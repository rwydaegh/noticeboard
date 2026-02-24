import fcntl
import logging
import re
import uuid
from functools import lru_cache

from django.conf import settings
from django.db.models import Q
from opensearchpy import OpenSearch, helpers

from .models import Opportunity
from .parsing import status

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def embedder():
    from fastembed import TextEmbedding
    from huggingface_hub import snapshot_download

    snapshot = snapshot_download(
        "qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q",
        revision="faf4aa4225822f3bc6376869cb1164e8e3feedd0",
        allow_patterns=["*.json", "*.txt", "*.onnx"],
        cache_dir=str(settings.MODEL_CACHE),
    )
    return TextEmbedding(
        specific_model_path=snapshot,
        model_name=settings.EMBEDDING_MODEL,
        cache_dir=str(settings.MODEL_CACHE),
        threads=2,
    )


def index_status():
    expected = Opportunity.objects.exclude(current=None).count()
    try:
        client = connection()
        documents = client.count(index=settings.SEARCH_INDEX)["count"]
        vectors = client.count(
            index=settings.SEARCH_INDEX, body={"query": {"exists": {"field": "embedding"}}}
        )["count"]
        return {
            "available": True,
            "documents": documents,
            "vectors": vectors,
            "expected": expected,
            "counts_match": documents == expected,
        }
    except Exception:
        return {
            "available": False,
            "documents": 0,
            "vectors": 0,
            "expected": expected,
            "counts_match": False,
        }


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
                    "model": settings.EMBEDDING_MODEL if vectors else None,
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
    if vectors:
        embeddings = embedder().embed(
            [d["title"] + "\n" + d["description"][:5000] for d in docs], batch_size=16
        )
        for doc, vector in zip(docs, embeddings, strict=True):
            doc["embedding"] = vector.tolist()
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
            if query and mode == "hybrid":
                candidate_limit = 200
                vector = next(embedder().query_embed(query)).tolist()
                knn = {"vector": vector, "k": 100}
                if country:
                    knn["filter"] = {"term": {"country": country}}
                response = client.search(
                    index=settings.SEARCH_INDEX,
                    body={"size": 100, "query": {"knn": {"embedding": knn}}},
                )
                semantic = [h["_source"]["opportunity_id"] for h in response["hits"]["hits"]]
                indexed_versions.update(
                    {
                        hit["_source"]["opportunity_id"]: hit["_source"]
                        for hit in response["hits"]["hits"]
                    }
                )
                if not semantic:
                    warnings.append("Keyword results only.")
                for items in (lexical[:100], semantic):
                    for rank, ident in enumerate(items, 1):
                        scores[ident] = scores.get(ident, 0) + 1 / (60 + rank)
                ranked = sorted(scores, key=lambda i: (-scores[i], i))
                backend = "OpenSearch BM25 + multilingual vectors"
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
