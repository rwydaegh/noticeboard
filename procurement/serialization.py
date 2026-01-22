from datetime import UTC, datetime

from .parsing import status


def serialize(opportunity, detail=False):
    notice = opportunity.current
    deadlines = [
        datetime.fromisoformat(lot["deadline"])
        for lot in notice.payload.get("lots", [])
        if lot.get("deadline")
    ]
    future = [d for d in deadlines if d > datetime.now(UTC)]
    next_deadline = min(future) if future else max(deadlines) if deadlines else None
    result = {
        "id": opportunity.pk,
        "publication_id": notice.publication_id,
        "title": notice.title,
        "description": notice.description,
        "buyer": notice.buyer,
        "country": notice.country,
        "published": notice.published.isoformat(),
        "kind": notice.kind,
        "status": status(notice.payload),
        "deadline": next_deadline.isoformat() if next_deadline else None,
        "language": notice.language,
        "quality": notice.quality,
        "source_url": f"https://ted.europa.eu/en/notice/-/detail/{notice.publication_id}",
        "cpv": notice.payload.get("cpv", []),
        "changed": bool(notice.payload.get("previous")),
        "warnings": notice.payload.get("warnings", []),
    }
    if detail:
        notices = sorted(
            opportunity.notices.all(),
            key=lambda n: (n.published, int(n.publication_id.split("-")[0])),
            reverse=True,
        )
        result.update(
            lots=[lot.payload for lot in notice.lots.all()],
            versions=[
                {
                    "publication_id": n.publication_id,
                    "published": n.published.isoformat(),
                    "kind": n.kind,
                    "title": n.title,
                    "checksum": n.checksum,
                    "quality": n.quality,
                }
                for n in notices
            ],
            changes=notice.payload.get("changes", []),
            previous=notice.payload.get("previous", []),
            documents=notice.payload.get("document_urls", []),
            retrieved_at=notice.retrieved_at.isoformat(),
            checksum=notice.checksum,
        )
    return result
