"""A bounded, overlapping daily import followed by a derived-index rebuild."""

import json
import os
from datetime import UTC, datetime, timedelta
from urllib.request import Request, urlopen

from airflow.sdk import dag, task


def post(path, payload):
    base = os.environ.get("NOTICEBOARD_URL", "http://127.0.0.1:8920").rstrip("/")
    token = os.environ["NOTICEBOARD_OPS_TOKEN"]
    request = Request(
        base + "/api/ops/" + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    with urlopen(request, timeout=600) as response:
        return json.load(response)


@dag(
    schedule="30 7 * * 1-5",
    start_date=datetime(2026, 3, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["ted", "noticeboard"],
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
)
def ted_daily():
    @task
    def import_notices(**context):
        interval_end = (
            context.get("data_interval_end") or context.get("logical_date") or datetime.now(UTC)
        )
        end = interval_end.date()
        start = end - timedelta(days=6)
        query = f'FT ~ "software" AND publication-date >= {start:%Y%m%d} AND publication-date <= {end:%Y%m%d} SORT BY publication-date DESC'
        result = post("sync", {"query": query, "limit": 500})
        if result["status"] not in {"complete", "bounded"}:
            raise RuntimeError(f"Incomplete import {result['id']}")
        return {"import_id": result["id"], "status": result["status"], "seen": result["seen"]}

    @task
    def rebuild_search(import_result):
        result = post("index?vectors=true", {})
        return {**import_result, **result}

    rebuild_search(import_notices())


ted_daily()
