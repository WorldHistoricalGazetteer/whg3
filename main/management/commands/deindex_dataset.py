# main.management.commands.deindex_dataset.py

import logging
from django.core.management.base import BaseCommand
from elastic.es_utils import removeDatasetFromIndex

logger = logging.getLogger('accession')

class Command(BaseCommand):
    help = 'Remove all places in dataset from ES index'

    def add_arguments(self, parser):
        parser.add_argument('dsid', type=int, help='Dataset ID to remove from ES index')

    def handle(self, *args, **options):
        dsid = options['dsid']
        logger.info(f'Starting removal of dataset {dsid}')
        try:
            msg = removeDatasetFromIndex(dsid=dsid)
            self.stdout.write(self.style.SUCCESS(f'Success: {msg}'))
        except Exception as e:
            logger.error(f'Error removing dataset {dsid}: {e}', exc_info=True)
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
