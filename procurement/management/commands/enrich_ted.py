"""Retrieve authoritative XML through a normal TED browser session."""

import time
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from procurement.ingestion import ingest
from procurement.models import ImportRun, Notice
from procurement.parsing import parse_xml


class Command(BaseCommand):
    help = "Enrich search records with TED XML. Install the browser extra and Chromium first."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=30)
        parser.add_argument("--publication", action="append", default=[])

    def handle(self, *args, **options):
        from playwright.sync_api import sync_playwright

        if not 1 <= options["limit"] <= 1000:
            raise CommandError("Limit must be 1–1000")
        records = Notice.objects.filter(quality="search").order_by("-published", "publication_id")
        ids = options["publication"] or list(
            records.values_list("publication_id", flat=True)[: options["limit"]]
        )
        if not ids:
            self.stdout.write("No records need XML enrichment")
            return
        run = ImportRun.objects.create(query=f"TED XML enrichment: {len(ids)} notices")
        try:
            with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto(
                    f"https://ted.europa.eu/en/notice/-/detail/{ids[0]}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_timeout(6000)
                for ident in ids:
                    try:
                        for attempt in range(4):
                            response = context.request.get(
                                f"https://ted.europa.eu/en/notice/{ident}/xml", timeout=60000
                            )
                            if response.status not in {202, 429, 503}:
                                break
                            time.sleep(4 * (attempt + 1))
                        if response.status != 200:
                            raise ValueError(f"TED XML HTTP {response.status}")
                        raw = response.body()
                        parsed = parse_xml(raw)
                        if parsed["publication_id"] != ident:
                            raise ValueError(
                                "Returned XML identifier does not match the requested notice"
                            )
                        _, outcome = database.submit(ingest, parsed, raw, "xml").result()
                        run.created += outcome == "created"
                        run.unchanged += outcome == "unchanged"
                    except Exception as exc:
                        run.errors.append({"record": ident, "error": str(exc)[:400]})
                    run.seen += 1
                    database.submit(run.save).result()
                    time.sleep(0.6)
                browser.close()
            run.status = "partial" if run.errors else "complete"
        except Exception as exc:
            run.errors.append({"error": str(exc)[:400]})
            run.status = "failed"
        finally:
            run.finished_at = timezone.now()
            run.save()
        self.stdout.write(
            f"Import {run.pk}: {run.status}; {run.seen} seen; {len(run.errors)} errors"
        )
        if run.errors:
            raise CommandError(str(run.errors[:3]))
