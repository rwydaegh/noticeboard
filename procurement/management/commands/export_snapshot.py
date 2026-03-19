import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from procurement.api import collection, run_json
from procurement.models import ImportRun, Opportunity
from procurement.serialization import serialize


class Command(BaseCommand):
    help = "Export only public source records for a static browser demo. No accounts or saved work."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        data = {
            "generated_at": timezone.now().isoformat(),
            "collection": collection(None),
            "notices": [
                serialize(obj, detail=True)
                for obj in Opportunity.objects.exclude(current=None)
                .select_related("current")
                .prefetch_related("notices", "current__lots")
            ],
            "imports": [run_json(run) for run in ImportRun.objects.order_by("-started_at")[:20]],
        }
        path = Path(options["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        self.stdout.write(f"Exported {len(data['notices'])} public procedures to {path}")
