import csv
import io
import secrets
from datetime import date

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import django_auth
from pydantic import Field

from .assistance import assist
from .exports import calendar
from .ingestion import sync_ted
from .models import ImportRun, Notice, Opportunity, Profile, SavedSearch, Watch
from .search import index_collection, index_status, retrieve, source_matches
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


@api.get("/notices/{ident}/source")
def source_record(request, ident: int, publication: str = ""):
    obj = opportunity(ident)
    notice = (
        get_object_or_404(Notice, opportunity=obj, publication_id=publication)
        if publication
        else obj.current
    )
    artifact = get_object_or_404(notice.artifacts, checksum=notice.checksum)
    return HttpResponse(
        artifact.content,
        content_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{notice.publication_id}.{artifact.format}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@api.get("/notices/{ident}/matches")
def matches(request, ident: int, q: str):
    return {"excerpts": source_matches(opportunity(ident).current, q[:500])}


@api.get("/notices/{ident}/calendar.ics")
def notice_calendar(request, ident: int):
    return HttpResponse(
        calendar([opportunity(ident).current]),
        content_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="deadline.ics"'},
    )


@api.get("/notices/{ident}/compare")
def compare_versions(request, ident: int, before: str, after: str):
    obj = opportunity(ident)
    old = get_object_or_404(Notice, opportunity=obj, publication_id=before)
    new = get_object_or_404(Notice, opportunity=obj, publication_id=after)
    return compare(old, new)


@api.get("/notices/{ident}/related")
def related(request, ident: int):
    obj = opportunity(ident)
    result = retrieve(obj.current.title[:500], mode="hybrid", limit=8)
    return {
        "items": [serialize(o) for o in result["items"] if o.pk != obj.pk][:5],
        "warnings": result["warnings"],
        "backend": result["backend"],
    }


class Question(Schema):
    question: str = Field(min_length=3, max_length=500)
    use_model: bool = False


@api.post("/notices/{ident}/ask", auth=django_auth)
def ask(request, ident: int, payload: Question):
    try:
        return assist(opportunity(ident).current, payload.question, payload.use_model)
    except ValueError as exc:
        raise HttpError(422, str(exc)) from exc
    except Exception as exc:
        raise HttpError(503, "The model request failed. Source excerpts remain available.") from exc


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


@api.get("/watch-calendar.ics", auth=django_auth)
def watch_calendar(request):
    watches = (
        Watch.objects.filter(user=request.user)
        .exclude(stage="pass")
        .exclude(opportunity__current=None)
        .select_related("opportunity__current")
    )
    return HttpResponse(
        calendar([w.opportunity.current for w in watches]),
        content_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saved-deadlines.ics"'},
    )


@api.get("/review-export", auth=django_auth)
def review_export(request):
    result = watchlist(request)
    return HttpResponse(
        __import__("json").dumps(result, ensure_ascii=False, indent=2),
        content_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="noticeboard-review.json"'},
    )


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


class ProfileInput(Schema):
    description: str = Field(default="", max_length=3000)
    countries: list[str] = Field(default_factory=list, max_length=50)
    exclusions: list[str] = Field(default_factory=list, max_length=30)


@api.get("/profile", auth=django_auth)
def get_profile(request):
    obj, _ = Profile.objects.get_or_create(user=request.user)
    return {
        "description": obj.description,
        "countries": obj.countries,
        "exclusions": obj.exclusions,
    }


@api.put("/profile", auth=django_auth)
def set_profile(request, payload: ProfileInput):
    Profile.objects.update_or_create(user=request.user, defaults=payload.dict())
    return {"saved": True}


@api.get("/recommendations", auth=django_auth)
def recommendations(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.description:
        return {"items": [], "warnings": ["Add a description of your work to find matches."]}
    result = retrieve(profile.description[:500], mode="hybrid", limit=100)
    items = []
    for obj in result["items"]:
        if profile.countries and obj.current.country not in profile.countries:
            continue
        haystack = (obj.current.title + " " + obj.current.description).lower()
        if any(ex.lower() in haystack for ex in profile.exclusions if ex):
            continue
        items.append(
            {**serialize(obj), "excerpts": source_matches(obj.current, profile.description)}
        )
    return {"items": items[:30], "warnings": result["warnings"], "backend": result["backend"]}


@api.get("/export.csv")
def export_csv(request, q: str = "", country: str = "", status: str = "", mode: str = "keyword"):
    if mode not in {"keyword", "hybrid"}:
        raise HttpError(400, "Unknown search mode")
    result = retrieve(q[:500], country[:3], status[:20], mode=mode, limit=1000)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        ["publication_id", "title", "buyer", "country", "status", "published", "source_url"]
    )
    for obj in result["items"]:
        row = serialize(obj)
        values = [
            str(row[k])
            for k in [
                "publication_id",
                "title",
                "buyer",
                "country",
                "status",
                "published",
                "source_url",
            ]
        ]
        writer.writerow(
            ["'" + v if v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in values]
        )
    return HttpResponse(
        stream.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="notices.csv"'},
    )


@api.get("/health")
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return {"status": "ok", "database": connection.vendor}


@api.get("/search-status")
def search_status(request):
    return index_status()


class SyncInput(Schema):
    query: str = Field(min_length=3, max_length=2000)
    limit: int = Field(default=100, ge=1, le=5000)


def check_ops(request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not settings.OPS_TOKEN or not secrets.compare_digest(token, settings.OPS_TOKEN):
        raise HttpError(403, "Operator token required")


@api.post("/ops/sync")
def sync(request, payload: SyncInput):
    check_ops(request)
    run = sync_ted(payload.query, payload.limit)
    if run.status in {"failed", "partial"}:
        raise HttpError(502, f"Import {run.pk} failed")
    return run_json(run)


@api.post("/ops/index")
def index(request, vectors: bool = False):
    check_ops(request)
    return {"indexed": index_collection(vectors)}
