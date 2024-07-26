# main/management/commands/ping_healthchecks.py
from django.core.management.base import BaseCommand
import requests

class Command(BaseCommand):
    help = 'Ping Healthchecks.io'

    def handle(self, *args, **kwargs):
        url = "https://hc-ping.com/2df5b739-8ffd-4810-a453-8507e5fe5c2d"
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.stdout.write(self.style.SUCCESS(f'Pinged Healthchecks.io successfully with status code {response.status_code}'))
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to ping Healthchecks.io: {e}'))
