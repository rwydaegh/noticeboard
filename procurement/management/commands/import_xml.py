import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from procurement.ingestion import import_xml


class Command(BaseCommand):
    help = "Import an eForms XML file or directory."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        path = Path(options["path"])
        files = sorted(path.glob("*.xml")) if path.is_dir() else [path]
        if not files:
            raise CommandError("No XML files found")
        run = import_xml(files)
        self.stdout.write(
            json.dumps(
                {
                    "id": run.pk,
                    "seen": run.seen,
                    "created": run.created,
                    "unchanged": run.unchanged,
                    "errors": run.errors,
                }
            )
        )
        if run.errors:
            raise CommandError("Some XML files failed")
