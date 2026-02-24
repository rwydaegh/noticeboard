from datetime import date

from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import django_auth
from pydantic import Field

from .models import ImportRun, Notice, Opportunity, SavedSearch, Watch
from .search import index_status, retrieve
from .serialization import compare, compare_payloads, serialize

api = NinjaAPI(title="Noticeboard API", version="0.1.0")


def opportunity(pk):
    return get_object_or_404(
        Opportunity.objects.select_related("current").exclude(current=None), pk=pk
    )


@api.get("/session")
def session(request):
    return {
        "user": request.user.get_username() if request.user.is_authenticated else None,
        "llm_available": False,
    }


@api.get("/notices")
def notices(
    request,
    q: str = "",
    country: str = "",
    status: str = "",
    mode: str = "keyword",
    limit: int = 40,
    offset: int = 0,
):
    if (
        len(q) > 500
        or len(country) > 3
        or mode not in {"keyword", "hybrid"}
        or not 1 <= limit <= 100
        or not 0 <= offset <= 2000
    ):
        raise HttpError(422, "Invalid search parameters")
    result = retrieve(q, country.upper(), status, mode, limit, offset)
    return {
        **{k: v for k, v in result.items() if k not in {"items", "scores"}},
        "items": [serialize(o) for o in result["items"]],
    }


@api.get("/notices/{ident}")
def detail(request, ident: int):
    return serialize(opportunity(ident), detail=True)


@api.get("/notices/{ident}/compare")
def compare_versions(request, ident: int, before: str, after: str):
    obj = opportunity(ident)
    old = get_object_or_404(Notice, opportunity=obj, publication_id=before)
    new = get_object_or_404(Notice, opportunity=obj, publication_id=after)
    return compare(old, new)


@api.get("/collection")
def collection(request):
    latest = ImportRun.objects.order_by("-started_at").first()
    return {
        "notices": Notice.objects.count(),
        "opportunities": Opportunity.objects.exclude(current=None).count(),
        "countries": sorted(
            set(Notice.objects.exclude(country="").values_list("country", flat=True))
        ),
        "xml_notices": Notice.objects.filter(quality="xml").count(),
        "latest_import": run_json(latest) if latest else None,
        "source": "TED",
        "today": date.today().isoformat(),
    }


def run_json(run):
    return {
        "id": run.pk,
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "seen": run.seen,
        "created": run.created,
        "unchanged": run.unchanged,
        "error_count": len(run.errors),
        "truncated": run.truncated,
        "source_total": run.source_total,
    }


class WatchInput(Schema):
    stage: str = Field(default="saved", pattern="^(saved|reviewing|pursue|pass)$")
    note: str = Field(default="", max_length=10000)
    mark_seen: bool = True


@api.get("/watchlist", auth=django_auth)
def watchlist(request):
    watches = (
        Watch.objects.filter(user=request.user)
        .select_related("opportunity__current")
        .order_by("-created_at")
    )
    return {
        "items": [
            {
                "opportunity": serialize(w.opportunity),
                "stage": w.stage,
                "note": w.note,
                "updated": w.seen_checksum != w.opportunity.current.checksum,
                "changes": compare_payloads(w.seen_payload, w.opportunity.current.payload)
                if w.seen_payload and w.seen_checksum != w.opportunity.current.checksum
                else None,
            }
            for w in watches
            if w.opportunity.current_id
        ]
    }


@api.get("/inbox", auth=django_auth)
def inbox(request):
    watches = (
        Watch.objects.filter(user=request.user)
        .exclude(opportunity__current=None)
        .select_related("opportunity__current", "seen_notice")
    )
    return {
        "items": [
            {
                "opportunity": serialize(w.opportunity),
                "stage": w.stage,
                "changes": compare_payloads(w.seen_payload, w.opportunity.current.payload)
                if w.seen_payload
                else None,
            }
            for w in watches
            if w.seen_checksum != w.opportunity.current.checksum
        ]
    }


@api.put("/watchlist/{ident}", auth=django_auth)
def save_watch(request, ident: int, payload: WatchInput):
    obj = opportunity(ident)
    values = {"stage": payload.stage, "note": payload.note}
    if payload.mark_seen:
        values["seen_notice"] = obj.current
        values["seen_checksum"] = obj.current.checksum
        values["seen_payload"] = obj.current.payload
    Watch.objects.update_or_create(user=request.user, opportunity=obj, defaults=values)
    return {"saved": True}


@api.delete("/watchlist/{ident}", auth=django_auth)
def delete_watch(request, ident: int):
    Watch.objects.filter(user=request.user, opportunity_id=ident).delete()
    return {"saved": False}


class SearchInput(Schema):
    name: str = Field(min_length=1, max_length=100)
    query: str = Field(default="", max_length=500)
    country: str = Field(default="", max_length=3)
    status: str = Field(default="", max_length=20)


@api.get("/saved-searches", auth=django_auth)
def saved_searches(request):
    return {
        "items": list(
            SavedSearch.objects.filter(user=request.user).values(
                "id", "name", "query", "country", "status"
            )
        )
    }


@api.post("/saved-searches", auth=django_auth)
def save_search(request, payload: SearchInput):
    obj = SavedSearch.objects.create(user=request.user, **payload.dict())
    return {"id": obj.pk}


@api.delete("/saved-searches/{ident}", auth=django_auth)
def delete_search(request, ident: int):
    obj = get_object_or_404(SavedSearch, user=request.user, pk=ident)
    obj.delete()
    return {"deleted": True}


@api.get("/search-status")
def search_status(request):
    return index_status()
