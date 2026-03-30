"""Measure known-item ranks on a declared development set; no automatic relevance claims."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noticeboard.settings")
import django

django.setup()
from procurement.models import Notice
from procurement.search import index_status, retrieve

root = Path(__file__).parent
spec = json.loads((root / "retrieval.json").read_text())
coverage = index_status()
if not coverage["counts_match"] or coverage["vectors"] != coverage["expected"]:
    raise SystemExit(f"Rebuild the full vector index before evaluation: {coverage}")
rows = []
for case in spec["cases"]:
    notice = Notice.objects.filter(publication_id=case["publication"]).first()
    row = {**case, "present": bool(notice), "results": {}}
    for mode in ["keyword", "hybrid"]:
        started = time.monotonic()
        result = retrieve(case["query"], mode=mode, limit=100)
        ids = [o.pk for o in result["items"]]
        rank = (
            ids.index(notice.opportunity_id) + 1
            if notice and notice.opportunity_id in ids
            else None
        )
        row["results"][mode] = {
            "rank": rank,
            "seconds": round(time.monotonic() - started, 3),
            "backend": result["backend"],
            "warnings": result["warnings"],
            "top5": [o.current.publication_id for o in result["items"][:5]],
        }
    rows.append(row)
summary = {}
for mode in ["keyword", "hybrid"]:
    ranks = [r["results"][mode]["rank"] for r in rows]
    summary[mode] = {
        "hit_at_5": sum(r is not None and r <= 5 for r in ranks) / len(ranks),
        "mrr_at_100": sum(1 / r if r else 0 for r in ranks) / len(ranks),
    }
output = {
    "kind": spec["kind"],
    "collection_notices": Notice.objects.count(),
    "index_coverage": coverage,
    "summary": summary,
    "cases": rows,
}
(root / "retrieval-results.json").write_text(json.dumps(output, indent=2))
print(json.dumps(summary, indent=2))
