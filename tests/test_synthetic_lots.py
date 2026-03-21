import copy
from datetime import UTC, datetime

from conftest import FIXTURE

from procurement.parsing import parse_xml, status
from procurement.serialization import compare_payloads


def test_changed_lot_deadline_is_reported_without_inventing_another():
    original = parse_xml(FIXTURE.read_bytes())
    original["lots"].append({"identifier": "LOT-0002", "deadline": None})
    changed = copy.deepcopy(original)
    changed["lots"][0]["deadline"] = "2026-04-04T11:00:00+01:00"
    fields = compare_payloads(original, changed)["fields"]
    assert len(fields) == 1 and fields[0]["field"] == "LOT-0001, deadline"
    assert changed["lots"][1]["deadline"] is None
    assert status(changed, datetime(2027, 1, 1, tzinfo=UTC)) == "deadline unverified"
