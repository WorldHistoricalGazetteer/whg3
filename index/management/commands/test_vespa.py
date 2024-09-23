# index/management/commands/test_vespa.py

from django.core.management.base import BaseCommand
from index.vespa import create_index#, test_vespa_connection
import sys
print(sys.path)


class Command(BaseCommand):
    help = 'Test connection to Vespa and create an index'

    def handle(self, *args, **kwargs):
        # connection_result = test_vespa_connection()
        # self.stdout.write(self.style.SUCCESS(f'Response from Vespa: {connection_result}'))

        index_result = create_index()
        self.stdout.write(self.style.SUCCESS(f'Index creation response: {index_result}'))
