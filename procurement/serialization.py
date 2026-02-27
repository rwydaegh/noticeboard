import difflib
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
        result["comparison"] = compare(notices[1], notice) if len(notices) > 1 else None
    return result


def compare(old, new):
    return compare_payloads(old.payload, new.payload)


def compare_payloads(old, new):
    fields = []
    for key in ["title", "buyer", "description", "kind", "country"]:
        a, b = old.get(key), new.get(key)
        if a != b:
            fields.append({"field": key, "before": a, "after": b})
    old_lots = {lot["identifier"]: lot for lot in old.get("lots", [])}
    new_lots = {lot["identifier"]: lot for lot in new.get("lots", [])}
    for ident in sorted(old_lots.keys() | new_lots.keys()):
        for field in [
            "title",
            "description",
            "deadline",
            "value",
            "currency",
            "documents",
            "requirements",
            "duration",
        ]:
            a, b = old_lots.get(ident, {}).get(field), new_lots.get(ident, {}).get(field)
            if a != b:
                fields.append({"field": f"{ident}, {field}", "before": a, "after": b})
    return {
        "before": old.get("publication_id"),
        "after": new.get("publication_id"),
        "fields": fields,
        "description_diff": list(
            difflib.unified_diff(
                old.get("description", "").splitlines(),
                new.get("description", "").splitlines(),
                lineterm="",
            )
        )[:200],
    }
