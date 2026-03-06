from .search import source_matches


def assist(notice, question, use_model=False):
    return {
        "publication_id": notice.publication_id,
        "source_url": f"https://ted.europa.eu/en/notice/-/detail/{notice.publication_id}",
        "question": question,
        "mode": "source excerpts",
        "claims": [{"answer": "", "quote": m["text"]} for m in source_matches(notice, question)],
        "unknown": [],
        "rejected_quotes": 0,
    }
