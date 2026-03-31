import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a local account and save its password in a private file."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="local")

    def handle(self, *args, **options):
        user, created = get_user_model().objects.get_or_create(
            username=options["username"], defaults={"is_staff": True}
        )
        if not created:
            self.stdout.write("Account already exists. Password unchanged")
            return
        password = secrets.token_urlsafe(18)
        user.set_password(password)
        user.save()
        folder = settings.PRIVATE_DIR
        folder.mkdir(exist_ok=True, mode=0o700)
        path = folder / "LOCAL_ACCESS.txt"
        path.write_text(f"Username: {user.username}\nPassword: {password}\n")
        path.chmod(0o600)
        self.stdout.write(f"Account created. Credentials: {path}")
