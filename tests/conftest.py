import json
from pathlib import Path

import pytest

from procurement.ingestion import ingest
from procurement.parsing import parse_search

FIXTURE = Path(__file__).parent / "fixtures/synthetic-search.json"


@pytest.fixture
def source():
    return parse_search(json.loads(FIXTURE.read_text()))


@pytest.fixture
def notice(db, source):
    return ingest(source, FIXTURE.read_bytes())[0]
