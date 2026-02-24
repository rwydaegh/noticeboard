from django.core.management.base import BaseCommand

from procurement.search import index_collection


class Command(BaseCommand):
    help = "Rebuild the derived search collection."

    def add_arguments(self, parser):
        parser.add_argument("--vectors", action="store_true")

    def handle(self, *args, **options):
        count = index_collection(options["vectors"])
        self.stdout.write(f"Indexed {count} current notices")
