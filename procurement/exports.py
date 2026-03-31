"""Portable review records and calendar events. No inferred deadlines."""

from datetime import UTC, datetime


def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold(line):
    lines, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 73:
            lines.append(current)
            current = " "
        current += char
    return "\r\n".join([*lines, current])


def calendar(notices):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Noticeboard//Procurement deadlines//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for notice in notices:
        if notice.payload.get("cancelled") or not notice.kind.startswith("cn-"):
            continue
        for lot in notice.lots.exclude(deadline=None):
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{notice.opportunity_id}-{escape(lot.identifier)}@noticeboard",
                    f"DTSTAMP:{stamp}",
                    "DTSTART:" + lot.deadline.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"),
                    "SUMMARY:" + escape(f"Tender deadline: {lot.title or notice.title}"),
                    "DESCRIPTION:"
                    + escape(
                        f"{notice.publication_id}, {lot.identifier}\nCheck the source documents for amendments before acting."
                    ),
                    "URL:https://ted.europa.eu/en/notice/-/detail/" + notice.publication_id,
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
