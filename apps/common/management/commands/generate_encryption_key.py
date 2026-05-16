"""Generate a fresh Fernet key suitable for DATA_ENCRYPTION_KEY."""

from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a new Fernet key (copy into DATA_ENCRYPTION_KEY)."

    def handle(self, *args, **options) -> None:
        key = Fernet.generate_key().decode("ascii")
        self.stdout.write(self.style.SUCCESS(key))
        self.stdout.write(
            self.style.WARNING(
                "Add to your .env:  DATA_ENCRYPTION_KEY=" + key
            )
        )
