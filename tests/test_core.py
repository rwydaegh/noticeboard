import copy
import json
from datetime import UTC, datetime

import httpx
import pytest
from conftest import FIXTURE
from defusedxml.common import EntitiesForbidden
from django.contrib.auth.models import User
from django.test import Client, override_settings

from procurement.assistance import Answer, validate_claims
from procurement.ingestion import ingest, request_page, sync_ted
from procurement.models import Artifact, Notice, Opportunity
from procurement.parsing import deadline, parse_search, parse_xml, status
from procurement.search import retrieve
from procurement.serialization import compare


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
    assert compare(old, latest)["fields"][0]["field"] == "title"


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


def test_saved_search_ownership_and_watch_isolation(notice):
    alice = User.objects.create_user("alice", password="test-pass")
    bob = User.objects.create_user("bob", password="test-pass")
    a, b = Client(), Client()
    a.force_login(alice)
    b.force_login(bob)
    ident = a.post(
        "/api/saved-searches",
        json.dumps({"name": "Private search"}),
        content_type="application/json",
    ).json()["id"]
    assert b.delete(f"/api/saved-searches/{ident}").status_code == 404
    a.put(
        f"/api/watchlist/{notice.opportunity_id}",
        json.dumps({"note": "Private note"}),
        content_type="application/json",
    )
    assert b.get("/api/watchlist").json()["items"] == []
    assert a.get("/api/watchlist").json()["items"][0]["note"] == "Private note"
    assert Client().get("/api/watchlist").status_code == 401


def test_same_publication_revision_appears_in_change_inbox(notice, source):
    user = User.objects.create_user("revision-reviewer")
    client = Client()
    client.force_login(user)
    client.put(f"/api/watchlist/{notice.opportunity_id}", "{}", content_type="application/json")
    source["title"] = "A corrected source title"
    ingest(source, b"synthetic revised source bytes", "xml")
    item = client.get("/api/inbox").json()["items"][0]
    assert item["changes"]["fields"][0]["field"] == "title"
    assert client.get("/api/watchlist").json()["items"][0]["updated"]
    client.put(f"/api/watchlist/{notice.opportunity_id}", "{}", content_type="application/json")
    assert client.get("/api/inbox").json()["items"] == []


def test_database_fallback_is_explicit(notice):
    with override_settings(SEARCH_URL="http://127.0.0.1:1"):
        result = retrieve(notice.title.split()[0])
    assert result["items"][0].pk == notice.opportunity_id
    assert result["backend"] == "database" and result["warnings"]


@pytest.mark.parametrize(
    "day,clock", [("2026-04-03", ""), ("2026-04-03", "11:00:00"), ("bad", "bad")]
)
def test_incomplete_deadlines_never_become_exact(day, clock):
    assert deadline(day, clock) is None


def test_mixed_lot_deadlines_do_not_claim_closed(source):
    source["lots"].append({"identifier": "LOT-0002", "deadline": None})
    assert status(source, datetime(2027, 1, 1, tzinfo=UTC)) == "deadline unverified"
    source["kind"] = "can-standard"
    assert status(source) == "award"
    source["cancelled"] = True
    assert status(source) == "cancelled"


def test_xml_entities_are_rejected():
    with pytest.raises(EntitiesForbidden):
        parse_xml(
            b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><ContractNotice>&secret;</ContractNotice>'
        )


def test_metadata_cannot_downgrade_authoritative_xml(notice, source):
    metadata = {
        **source,
        "quality": "search",
        "procedure": "incomplete",
        "title": "Incomplete metadata",
    }
    assert ingest(metadata, metadata)[1] == "unchanged"
    notice.refresh_from_db()
    assert notice.quality == "xml"
    assert notice.title != metadata["title"]


def test_csv_formula_injection_is_neutralized(notice):
    notice.title = '=HYPERLINK("https://example.invalid")'
    notice.save()
    with override_settings(SEARCH_URL=""):
        response = Client().get("/api/export.csv")
    assert b"'=HYPERLINK" in response.content


def test_quote_validation_rejects_invented_evidence():
    answer = Answer.model_validate(
        {
            "claims": [
                {"answer": "Stated", "quote": "The term is twenty four months."},
                {"answer": "Invented", "quote": "No certifications are required."},
            ]
        }
    )
    accepted, rejected = validate_claims(answer, "The term is twenty  four months.")
    assert len(accepted) == 1 and rejected == 1
