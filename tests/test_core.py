import pytest
from conftest import FIXTURE

from procurement.ingestion import ingest
from procurement.models import Artifact, Notice
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
def test_importing_the_same_record_twice_is_harmless(source):
    notice, state = ingest(source, FIXTURE.read_bytes())
    assert state == "created"
    assert ingest(source, FIXTURE.read_bytes())[1] == "unchanged"
    assert Notice.objects.count() == Artifact.objects.count() == 1
