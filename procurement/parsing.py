import hashlib
import json
import re
from datetime import UTC, date, datetime
from html import unescape
from urllib.parse import urlsplit


def clean(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def safe_url(value):
    value = str(value or "").strip()
    try:
        parts = urlsplit(value)
        return value if parts.scheme in {"http", "https"} and parts.netloc else ""
    except ValueError:
        return ""


def values(value):
    return value if isinstance(value, list) else [value] if value else []


def text(value, language="eng"):
    if isinstance(value, dict):
        value = value.get(language) or next(iter(value.values()), "")
    if isinstance(value, list):
        return "\n".join(clean(v) for v in value if v)
    return clean(value)


def publication(value):
    match = re.fullmatch(r"0*(\d+)-(\d{4})", str(value))
    if not match:
        raise ValueError(f"Invalid publication identifier: {value!r}")
    return f"{int(match[1])}-{match[2]}"


def iso_date(value):
    return date.fromisoformat(str(value)[:10])


def parse_search(record):
    ident = publication(record.get("publication-number", ""))
    description = text(record.get("description-proc")) or text(record.get("description-lot"))
    # Search arrays do not preserve lot associations.
    return {
        "publication_id": ident,
        "reference": text(record.get("notice-identifier")),
        "procedure": text(record.get("procedure-identifier")) or ident,
        "published": iso_date(record["publication-date"]).isoformat(),
        "title": text(record.get("notice-title")) or ident,
        "description": description,
        "buyer": text(record.get("buyer-name")),
        "country": (values(record.get("buyer-country")) or [""])[0],
        "kind": text(record.get("notice-type")),
        "language": text(record.get("official-language")).lower(),
        "deadline": None,
        "cpv": values(record.get("classification-cpv")),
        "lots": [],
        "changes": [text(record.get("change-description"))]
        if record.get("change-description")
        else [],
        "previous": values(record.get("change-notice-version-identifier")),
        "cancelled": "cancel" in (record.get("change-reason-code") or []),
        "quality": "search",
        "warnings": [
            "Search metadata only. Lot details and exact deadlines need the source notice."
        ],
        "document_urls": [
            url for value in values(record.get("document-url-lot")) if (url := safe_url(value))
        ],
        "source_deadlines": record.get("deadline-receipt-tender-date-lot") or [],
    }


def checksum(raw):
    if not isinstance(raw, bytes):
        raw = json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def status(payload, now=None):
    now = now or datetime.now(UTC)
    kind = payload.get("kind", "")
    if payload.get("cancelled"):
        return "cancelled"
    if kind.startswith("can-") or kind in {"veat", "can-modif"}:
        return "award" if kind != "veat" else "direct award"
    if kind.startswith("pin-") and "cfc" not in kind:
        return "planning"
    if kind.startswith("cn-") or kind in {"qu-sy", "pin-cfc-standard", "pin-cfc-social"}:
        dates = [
            datetime.fromisoformat(lot["deadline"])
            for lot in payload.get("lots", [])
            if lot.get("deadline")
        ]
        if any(d > now for d in dates):
            return "open"
        if dates and len(dates) == len(payload.get("lots", [])):
            return "closed"
        return "deadline unverified"
    return "other"
