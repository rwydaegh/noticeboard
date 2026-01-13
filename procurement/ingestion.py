import json
import logging

from django.db import transaction

from .models import Artifact, Lot, Notice, Opportunity
from .parsing import checksum

log = logging.getLogger(__name__)


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
    candidate = notice
    if opportunity.current_id != candidate.id:
        opportunity.current = candidate
        opportunity.save(update_fields=["current", "updated_at"])
    return notice, "created" if created else "updated"
