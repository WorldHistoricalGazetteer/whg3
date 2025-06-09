import logging

from django.core.management.base import BaseCommand

from elastic.es_utils import removeDatasetFromIndex

logger = logging.getLogger('accession')


class Command(BaseCommand):
    help = 'Remove all places in dataset from ES index, with throttling'

    def add_arguments(self, parser):
        parser.add_argument('dsid', type=int, help='Dataset ID to remove from ES index')
        parser.add_argument(
            '--throttle', type=float, default=0.1,
            help='Throttle delay in seconds between ES calls (default 0.1)'
        )

    def handle(self, *args, **options):
        dsid = options['dsid']
        throttle = options['throttle']
        logger.info(f'Starting removal of dataset {dsid} with throttle {throttle}s')
        try:
            msg = removeDatasetFromIndex(dsid, throttle_delay=throttle)
            self.stdout.write(self.style.SUCCESS(f'Success: {msg}'))
        except Exception as e:
            logger.error(f'Error removing dataset {dsid}: {e}', exc_info=True)
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
