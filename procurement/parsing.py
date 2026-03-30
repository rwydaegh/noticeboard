"""Source adapters. XML retains lot boundaries; search records do not invent them."""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import urlsplit

from defusedxml import ElementTree as ET


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


def deadline(day, clock=""):
    if not day:
        return None
    day, clock = str(day), str(clock or "")
    if not clock:
        return None
    try:
        offset = day[10:] if len(day) > 10 else ""
        if not re.search(r"Z$|[+-]\d\d:\d\d$", clock):
            clock += offset
        result = datetime.fromisoformat(day[:10] + "T" + clock.replace("Z", "+00:00"))
        return result.isoformat() if result.tzinfo else None
    except ValueError:
        return None


def amount(value):
    try:
        d = Decimal(str(value))
        return str(d) if d.is_finite() and abs(d) < Decimal("1e22") else None
    except (InvalidOperation, ValueError):
        return None


def find(node, path):
    return clean(node.findtext(path, default=""))


def parse_xml(raw):
    if len(raw) > 10_000_000:
        raise ValueError("Notice exceeds 10 MB")
    root = ET.fromstring(raw)
    if root.tag.rsplit("}", 1)[-1] not in {
        "ContractNotice",
        "ContractAwardNotice",
        "PriorInformationNotice",
    }:
        raise ValueError("Only eForms notice XML is supported")
    ident = publication(find(root, ".//{*}NoticePublicationID"))
    published = iso_date(find(root, ".//{*}PublicationDate")).isoformat()
    project = root.find("{*}ProcurementProject")
    if project is None:
        raise ValueError("Missing procurement project")
    companies = {}
    for company in root.findall(".//{*}Organizations/{*}Organization/{*}Company"):
        companies[find(company, "{*}PartyIdentification/{*}ID")] = company
    buyer_id = find(root, "{*}ContractingParty/{*}Party/{*}PartyIdentification/{*}ID")
    buyer_node = companies.get(buyer_id)
    buyer = find(buyer_node, "{*}PartyName/{*}Name") if buyer_node is not None else ""
    country = (
        find(buyer_node, "{*}PostalAddress/{*}Country/{*}IdentificationCode")
        if buyer_node is not None
        else ""
    )
    lots = []
    for lot in root.findall("{*}ProcurementProjectLot"):
        period = lot.find("{*}TenderingProcess/{*}TenderSubmissionDeadlinePeriod")
        if period is None:
            period = lot.find("{*}TenderingProcess/{*}ParticipationRequestReceptionPeriod")
        day = find(period, "{*}EndDate") if period is not None else ""
        clock = find(period, "{*}EndTime") if period is not None else ""
        value_node = lot.find(
            "{*}ProcurementProject/{*}RequestedTenderTotal/{*}EstimatedOverallContractAmount"
        )
        duration_node = lot.find("{*}ProcurementProject/{*}PlannedPeriod/{*}DurationMeasure")
        duration = {"value": clean(duration_node.text), "unit": duration_node.attrib.get("unitCode", "")} if duration_node is not None else None
        documents = [
            url
            for e in lot.findall(
                ".//{*}CallForTendersDocumentReference/{*}Attachment/{*}ExternalReference/{*}URI"
            )
            if (url := safe_url(e.text))
        ]
        requirements = [
            clean(e.text)
            for e in lot.findall(".//{*}TendererQualificationRequest//{*}Description")
            if e.text
        ]
        lots.append(
            {
                "identifier": find(lot, "{*}ID"),
                "title": find(lot, "{*}ProcurementProject/{*}Name"),
                "description": find(lot, "{*}ProcurementProject/{*}Description"),
                "deadline": deadline(day, clock),
                "duration": duration,
                "deadline_date": day,
                "value": amount(value_node.text) if value_node is not None else None,
                "currency": value_node.attrib.get("currencyID", "")
                if value_node is not None
                else "",
                "documents": documents,
                "requirements": requirements,
                "cpv": sorted(
                    {clean(e.text) for e in lot.findall(".//{*}ItemClassificationCode") if e.text}
                ),
            }
        )
    exact_deadlines = [lot["deadline"] for lot in lots if lot["deadline"]]
    cpv = sorted({clean(e.text) for e in project.findall(".//{*}ItemClassificationCode") if e.text})
    notice_id = find(root, "{*}ID")
    version = find(root, "{*}VersionID")
    return {
        "publication_id": ident,
        "reference": f"{notice_id}-{version}",
        "procedure": find(root, "{*}ContractFolderID") or notice_id,
        "published": published,
        "title": find(project, "{*}Name"),
        "description": find(project, "{*}Description"),
        "buyer": buyer,
        "country": country,
        "kind": find(root, "{*}NoticeTypeCode"),
        "language": find(root, "{*}NoticeLanguageCode").lower(),
        "deadline": min(exact_deadlines, key=datetime.fromisoformat) if exact_deadlines else None,
        "cpv": cpv,
        "lots": lots,
        "changes": [clean(e.text) for e in root.findall(".//{*}ChangeDescription") if e.text],
        "previous": [
            clean(e.text) for e in root.findall(".//{*}ChangedNoticeIdentifier") if e.text
        ],
        "cancelled": any(
            clean(e.text) == "cancel"
            for e in root.findall(".//{*}Changes/{*}ChangeReason/{*}ReasonCode")
        ),
        "quality": "xml",
        "warnings": [],
    }


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
        "language": text((values(record.get("official-language")) or [""])[0]).lower(),
        "languages": values(record.get("official-language")),
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
