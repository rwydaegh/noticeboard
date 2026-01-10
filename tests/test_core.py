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
