from django.test import Client

from procurement.ingestion import ingest


def test_version_comparison_cannot_mix_procedures(notice, source):
    other = {**source, "publication_id": "123-2026", "procedure": "different"}
    ingest(other, b"synthetic unrelated record", "xml")
    response = Client().get(
        f"/api/notices/{notice.opportunity_id}/compare",
        {"before": "123-2026", "after": notice.publication_id},
    )
    assert response.status_code == 404
