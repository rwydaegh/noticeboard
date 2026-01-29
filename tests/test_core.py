import copy

import httpx
import pytest
from conftest import FIXTURE
from django.contrib.auth.models import User
from django.test import Client

from procurement.ingestion import ingest, request_page, sync_ted
from procurement.models import Artifact, Notice, Opportunity
from procurement.parsing import parse_search, status


def test_search_arrays_are_not_invented_lots():
    record = {
        "publication-number": "000123-2026",
        "publication-date": "2026-01-09",
        "notice-title": {"eng": "Test"},
        "buyer-country": ["BEL"],
        "notice-type": "cn-standard",
        "deadline-receipt-tender-date-lot": ["2026-10-01", "2026-11-01"],
    }
    parsed = parse_search(record)
    assert parsed["publication_id"] == "123-2026"
    assert parsed["lots"] == [] and parsed["deadline"] is None
    assert status(parsed) == "deadline unverified"


@pytest.mark.django_db
def test_repeat_import_and_historical_arrival(source):
    latest, outcome = ingest(source, FIXTURE.read_bytes(), "xml")
    assert outcome == "created"
    assert ingest(source, FIXTURE.read_bytes(), "xml")[1] == "unchanged"
    earlier = copy.deepcopy(source)
    earlier.update(publication_id="100-2026", published="2026-01-01", title="Earlier title")
    old, _ = ingest(earlier, b"synthetic earlier version", "xml")
    latest.opportunity.refresh_from_db()
    assert latest.opportunity.current_id == latest.id
    assert Notice.objects.count() == Artifact.objects.count() == 2
    assert Opportunity.objects.count() == 1


def test_retry_after_and_timeout_are_visible():
    attempts, sleeps = [], []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"timedOut": True})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="incomplete"),
    ):
        request_page(client, {}, sleep=sleeps.append)
    assert len(attempts) == 2 and sleeps == [2]


@pytest.mark.django_db
def test_bad_record_is_quarantined_and_cursor_loop_fails():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "notices": [{"publication-number": "invalid"}],
                "iterationNextToken": "same",
                "totalNoticeCount": 20,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run = sync_ted("test", 10, client=client)
    assert run.status == "failed"
    assert run.seen == 2
    assert any("repeated" in e.get("error", "") for e in run.errors)


def test_mutation_requires_csrf(notice):
    user = User.objects.create_user("csrf-user")
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    url = f"/api/watchlist/{notice.opportunity_id}"
    assert client.put(url, "{}", content_type="application/json").status_code == 403
    token = client.get("/auth/csrf").json()["csrfToken"]
    assert (
        client.put(url, "{}", content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )


def test_watch_ownership(notice):
    alice, bob = User.objects.create_user("alice"), User.objects.create_user("bob")
    a, b = Client(), Client()
    a.force_login(alice)
    b.force_login(bob)
    a.put(
        f"/api/watchlist/{notice.opportunity_id}",
        '{"note":"Private"}',
        content_type="application/json",
    )
    assert b.get("/api/watchlist").json()["items"] == []
    assert Client().get("/api/watchlist").status_code == 401
