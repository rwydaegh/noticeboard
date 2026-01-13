import json

from django.core.management.base import BaseCommand, CommandError

from procurement.ingestion import sync_ted


class Command(BaseCommand):
    help = "Import a bounded TED search. Repeating a query does not duplicate notices."

    def add_arguments(self, parser):
        parser.add_argument("query")
        parser.add_argument("--limit", type=int, default=250)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 10000:
            raise CommandError("Use a limit between 1 and 10000")
        run = sync_ted(options["query"], options["limit"])
        self.stdout.write(
            json.dumps(
                {
                    "id": run.pk,
                    "status": run.status,
                    "seen": run.seen,
                    "created": run.created,
                    "unchanged": run.unchanged,
                    "errors": run.errors,
                    "truncated": run.truncated,
                }
            )
        )
        if run.status in {"failed", "partial"}:
            raise CommandError("Import incomplete; inspect the run record")
