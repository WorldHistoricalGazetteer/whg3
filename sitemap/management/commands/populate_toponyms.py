# sitemap/management/commands/populate_toponyms.py
from django.core.management.base import BaseCommand
from sitemap.tasks import populate_toponyms

class Command(BaseCommand):
    help = 'Populate the toponyms table'

    def handle(self, *args, **kwargs):
        populate_toponyms.delay()  # Trigger the Celery task
        self.stdout.write(self.style.SUCCESS('Toponyms population task has been triggered.'))
