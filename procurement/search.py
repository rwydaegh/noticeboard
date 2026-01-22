import re

from django.db.models import Q

from .models import Opportunity
from .parsing import status


def retrieve(query="", country="", state="", mode="keyword", limit=50, offset=0):
    rows = Opportunity.objects.exclude(current=None).select_related("current")
    if country:
        rows = rows.filter(current__country=country)
    if query:
        predicate = Q()
        for word in re.findall(r"\w+", query)[:20]:
            predicate |= (
                Q(current__title__icontains=word)
                | Q(current__description__icontains=word)
                | Q(current__buyer__icontains=word)
            )
        rows = rows.filter(predicate)
    items = list(rows.order_by("-current__published", "-current_id")[:2000])
    if state:
        items = [o for o in items if status(o.current.payload) == state]
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "backend": "database",
        "warnings": [],
        "scores": {},
        "candidate_limit": 2000,
    }
