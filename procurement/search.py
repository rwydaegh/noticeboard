import fcntl
import logging
import re
import uuid

from django.conf import settings
from django.db.models import Q
from opensearchpy import OpenSearch, helpers

from .models import Opportunity
from .parsing import status

log = logging.getLogger(__name__)


def connection():
    return OpenSearch(settings.SEARCH_URL, timeout=15, max_retries=2, retry_on_timeout=True)


def document(notice):
    return {
        "opportunity_id": notice.opportunity_id,
        "notice_id": notice.pk,
        "checksum": notice.checksum,
        "title": notice.title,
        "description": notice.description,
        "buyer": notice.buyer,
        "country": notice.country,
        "kind": notice.kind,
        "published": notice.published.isoformat(),
        "cpv": notice.payload.get("cpv", []),
    }


def index_collection(vectors=False):
    with (settings.RUNTIME_DIR / "index.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _build_index(vectors)


def _build_index(vectors):
    client = connection()
    alias = settings.SEARCH_INDEX
    generation = alias + "-" + uuid.uuid4().hex
    client.indices.create(
        index=generation,
        body={
            "settings": {"index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}},
            "mappings": {
                "_meta": {
                    "vectors": vectors,
                    "model": None,
                },
                "properties": {
                    "opportunity_id": {"type": "integer"},
                    "notice_id": {"type": "integer"},
                    "checksum": {"type": "keyword"},
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "buyer": {"type": "text"},
                    "country": {"type": "keyword"},
                    "kind": {"type": "keyword"},
                    "cpv": {"type": "keyword"},
                    "published": {"type": "date"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"},
                    },
                },
            },
        },
    )
    try:
        opportunities = Opportunity.objects.exclude(current=None).select_related("current")
        total, batch = 0, []
        for opportunity in opportunities.iterator(chunk_size=50):
            batch.append(opportunity.current)
            if len(batch) == 32:
                total += _index_batch(client, batch, vectors, generation)
                batch = []
        total += _index_batch(client, batch, vectors, generation)
        client.indices.refresh(index=generation)
        old = (
            list(client.indices.get_alias(name=alias))
            if client.indices.exists_alias(name=alias)
            else []
        )
        actions = [{"remove": {"index": name, "alias": alias}} for name in old]
        actions.append({"add": {"index": generation, "alias": alias}})
        client.indices.update_aliases(body={"actions": actions})
    except Exception:
        client.indices.delete(index=generation, ignore=[404])
        raise
    for name in old:
        try:
            client.indices.delete(index=name)
        except Exception:
            log.warning("Could not remove retired derived index %s", name)
    return total


def _index_batch(client, notices, vectors, generation):
    if not notices:
        return 0
    docs = [document(n) for n in notices]
    actions = [{"_index": generation, "_id": d["opportunity_id"], "_source": d} for d in docs]
    helpers.bulk(client, actions)
    return len(docs)


def _filters(country, kind):
    filters = []
    if country:
        filters.append({"term": {"country": country}})
    if kind:
        filters.append({"term": {"kind": kind}})
    return filters


def retrieve(query="", country="", state="", mode="keyword", limit=50, offset=0):
    warnings = []
    backend = "database"
    ranked = None
    scores = {}
    indexed_versions = {}
    candidate_limit = 1000
    if settings.SEARCH_URL:
        try:
            client = connection()
            boolean = {"filter": _filters(country, "")}
            boolean["must"] = (
                [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "description", "buyer"],
                            "type": "best_fields",
                            "operator": "or",
                        }
                    }
                ]
                if query
                else [{"match_all": {}}]
            )
            response = client.search(
                index=settings.SEARCH_INDEX,
                body={
                    "size": 1000,
                    "query": {"bool": boolean},
                    **({"sort": [{"published": "desc"}]} if not query else {}),
                },
            )
            lexical = [hit["_source"]["opportunity_id"] for hit in response["hits"]["hits"]]
            indexed_versions.update(
                {
                    hit["_source"]["opportunity_id"]: hit["_source"]
                    for hit in response["hits"]["hits"]
                }
            )
            ranked = lexical
            backend = "OpenSearch BM25"
        except Exception:
            log.exception("Search unavailable; using database retrieval")
            ranked = None
            warnings.append("Basic search.")
    queryset = Opportunity.objects.exclude(current=None).select_related("current")
    if country:
        queryset = queryset.filter(current__country=country)
    if ranked is not None:
        objects = {o.pk: o for o in queryset.filter(pk__in=ranked)}
        opportunities = [
            objects[i]
            for i in ranked
            if i in objects and indexed_versions[i].get("checksum") == objects[i].current.checksum
        ]
        if len(opportunities) < len(objects):
            warnings.append("Updated notices are missing from these results.")
    else:
        if query:
            predicate = Q()
            for word in re.findall(r"\w+", query)[:20]:
                predicate |= (
                    Q(current__title__icontains=word)
                    | Q(current__description__icontains=word)
                    | Q(current__buyer__icontains=word)
                )
            queryset = queryset.filter(predicate)
        opportunities = list(queryset.order_by("-current__published", "-current_id")[:2000])
    if state:
        opportunities = [o for o in opportunities if status(o.current.payload) == state]
    return {
        "items": opportunities[offset : offset + limit],
        "total": len(opportunities),
        "backend": backend,
        "warnings": warnings,
        "scores": scores,
        "candidate_limit": candidate_limit if ranked is not None else 2000,
    }
