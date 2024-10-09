# ingestion/management/commands/ingest_places.py

from django.core.management.base import BaseCommand
from ingestion.tasks import ingest_gzipped_data_from_url  # Import the shared task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ingest places from a remote dataset'

    def add_arguments(self, parser):
        parser.add_argument('dataset_name', type=str,
                            help='The name of the dataset (e.g., "Pleiades", "GeoNames", "Wikidata", "TGN")')
        parser.add_argument('--limit', type=int, default=None, help='Limit the number of items to ingest')

    def handle(self, *args, **kwargs):
        dataset_name = kwargs['dataset_name']
        limit = kwargs.get('limit')

        # Call the Celery task for ingestion
        ingest_gzipped_data_from_url.delay(dataset_name, limit)

        self.stdout.write(self.style.SUCCESS(f'Successfully initiated ingestion for dataset: {dataset_name}'))
