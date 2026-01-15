import json
import logging
import time

import httpx
from django.db import transaction
from django.utils import timezone

from .models import Artifact, ImportRun, Lot, Notice, Opportunity
from .parsing import checksum, parse_search

log = logging.getLogger(__name__)
TED_API = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = [
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "notice-type",
    "notice-identifier",
    "procedure-identifier",
    "description-proc",
    "description-lot",
    "classification-cpv",
    "document-url-lot",
    "deadline-receipt-tender-date-lot",
    "change-description",
    "change-notice-version-identifier",
    "change-reason-code",
    "official-language",
]


def request_page(client, payload, sleep=time.sleep):
    response = client.post(TED_API, json=payload)
    response.raise_for_status()
    return response.json()


def ordering(notice):
    return (notice.published, int(notice.publication_id.split("-")[0]))


@transaction.atomic
def ingest(parsed, raw, format="json"):
    digest = checksum(raw)
    existing = Notice.objects.filter(publication_id=parsed["publication_id"]).first()
    key = "ted:" + parsed["procedure"]
    opportunity, _ = Opportunity.objects.get_or_create(source_key=key)
    opportunity = Opportunity.objects.select_for_update().get(pk=opportunity.pk)
    if existing and existing.checksum == digest and existing.payload == parsed:
        return existing, "unchanged"
    defaults = {
        k: parsed[k]
        for k in [
            "reference",
            "published",
            "title",
            "description",
            "buyer",
            "country",
            "kind",
            "language",
            "deadline",
            "quality",
        ]
    }
    defaults.update(opportunity=opportunity, payload=parsed, checksum=digest)
    notice, created = Notice.objects.update_or_create(
        publication_id=parsed["publication_id"], defaults=defaults
    )
    Artifact.objects.get_or_create(
        notice=notice,
        checksum=digest,
        defaults={
            "content": raw.decode()
            if isinstance(raw, bytes)
            else json.dumps(raw, ensure_ascii=False),
            "format": format,
        },
    )
    notice.lots.all().delete()
    Lot.objects.bulk_create(
        [
            Lot(
                notice=notice,
                identifier=lot["identifier"],
                title=lot["title"],
                description=lot["description"],
                deadline=lot["deadline"],
                value=lot["value"],
                currency=lot["currency"],
                payload=lot,
            )
            for lot in parsed.get("lots", [])
        ]
    )
    notice.refresh_from_db()
    candidate = max(opportunity.notices.all(), key=ordering)
    if opportunity.current_id != candidate.id:
        opportunity.current = candidate
        opportunity.save(update_fields=["current", "updated_at"])
    return notice, "created" if created else "updated"


def sync_ted(query, limit=250, client=None):
    run = ImportRun.objects.create(query=query)
    owned = client is None
    client = client or httpx.Client(
        timeout=45, headers={"User-Agent": "Noticeboard/0.1 (public procurement reuse)"}
    )
    try:
        token = None
        while run.seen < limit:
            request = {
                "query": query,
                "fields": FIELDS,
                "limit": min(100, limit - run.seen),
                "scope": "ALL",
                "paginationMode": "ITERATION",
                "checkQuerySyntax": False,
            }
            if token:
                request["iterationNextToken"] = token
            body = request_page(client, request)
            if body.get("totalNoticeCount") is not None:
                run.source_total = body["totalNoticeCount"]
            records = body.get("notices", [])
            for record in records:
                _, outcome = ingest(parse_search(record), record)
                run.created += outcome == "created"
                run.unchanged += outcome == "unchanged"
                run.seen += 1
            token = body.get("iterationNextToken")
            run.cursor = token or ""
            run.save()
            if not records or not token:
                break
        run.truncated = bool(
            token
            and run.seen >= limit
            and (run.source_total is None or run.seen < run.source_total)
        )
        run.status = "partial" if run.errors else "bounded" if run.truncated else "complete"
    except Exception as exc:
        log.exception("Import %s failed", run.pk)
        run.errors.append({"error": str(exc)[:400]})
        run.status = "failed"
    finally:
        if owned:
            client.close()
        run.finished_at = timezone.now()
        run.save()
    return run
