from unittest.mock import MagicMock, patch

import pytest
from django.test import Client

from procurement.ingestion import ingest
from procurement.search import index_collection


def test_version_comparison_cannot_mix_procedures(notice, source):
    other = {**source, "publication_id": "123-2026", "procedure": "different"}
    ingest(other, b"synthetic unrelated record", "xml")
    response = Client().get(
        f"/api/notices/{notice.opportunity_id}/compare",
        {"before": "123-2026", "after": notice.publication_id},
    )
    assert response.status_code == 404


def test_failed_index_build_keeps_current_alias(notice):
    client = MagicMock()
    with (
        patch("procurement.search.connection", return_value=client),
        patch("procurement.search._index_batch", side_effect=RuntimeError("injected bulk failure")),
        pytest.raises(RuntimeError, match="injected"),
    ):
        index_collection(False)
    client.indices.update_aliases.assert_not_called()
    client.indices.delete.assert_called_once()


def test_successful_index_build_switches_alias_after_refresh(notice):
    client = MagicMock()
    client.indices.exists_alias.return_value = True
    client.indices.get_alias.return_value = {"old-generation": {}}
    with (
        patch("procurement.search.connection", return_value=client),
        patch("procurement.search._index_batch", return_value=1),
    ):
        assert index_collection(False) == 1
    calls = [call[0] for call in client.indices.mock_calls]
    assert calls.index("refresh") < calls.index("update_aliases") < calls.index("delete")
