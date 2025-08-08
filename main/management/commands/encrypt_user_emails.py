from django.core.management.base import BaseCommand
from users.models import User

class Command(BaseCommand):
    help = "Encrypts existing email values for all users"

    def handle(self, *args, **kwargs):
        updated = 0
        for user in User.objects.exclude(email__isnull=True).exclude(email=""):
            original = user.email
            user.email = original  # Triggers encryption on save
            user.save(update_fields=["email"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Encrypted {updated} user emails."))
