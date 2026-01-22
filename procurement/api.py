from datetime import date

from django.shortcuts import get_object_or_404
from ninja import NinjaAPI
from ninja.errors import HttpError

from .models import ImportRun, Notice, Opportunity
from .search import retrieve
from .serialization import serialize

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
