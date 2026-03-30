from pathlib import Path

import pytest

from procurement.ingestion import ingest
from procurement.parsing import parse_xml

FIXTURE = Path(__file__).parent / "fixtures/666712-2026.xml"


@pytest.fixture
def source():
    return parse_xml(FIXTURE.read_bytes())


@pytest.fixture
def notice(db, source):
    return ingest(source, FIXTURE.read_bytes(), "xml")[0]
