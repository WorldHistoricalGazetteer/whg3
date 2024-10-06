# main/management/commands/refresh_mapdata_cache.py

from django.core.management.base import BaseCommand
from collection.models import Collection
from datasets.models import Dataset
from utils.mapdata import mapdata_task


class Command(BaseCommand):
    help = 'Refresh mapdata for all Datasets and Collections or a specific Dataset or Collection'

    def add_arguments(self, parser):
        parser.add_argument(
            'type',
            choices=['dataset', 'collection'],
            help='Type of the entity to refresh: either "dataset" or "collection"'
        )
        parser.add_argument(
            'id',
            type=int,
            nargs='?',
            help='ID of the Dataset or Collection to refresh mapdata for (optional for all)'
        )

    def handle(self, *args, **options):
        entity_type = options['type']
        entity_id = options['id']

        if entity_type == 'dataset':
            if entity_id is not None:
                try:
                    dataset = Dataset.objects.get(id=entity_id, core=False)
                    mapdata_task.delay('datasets', dataset.id, 'standard', refresh=True)
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully scheduled mapdata refresh for Dataset ID {entity_id}'))
                except Dataset.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Dataset with ID {entity_id} does not exist or is a core dataset'))
            else:
                # Fetch all Datasets excluding those with core=True
                datasets = Dataset.objects.filter(core=False)
                for dataset in datasets:
                    mapdata_task.delay('datasets', dataset.id, 'standard', refresh=True)
                self.stdout.write(self.style.SUCCESS('Successfully scheduled mapdata refresh for all Datasets'))

        elif entity_type == 'collection':
            if entity_id is not None:
                try:
                    collection = Collection.objects.get(id=entity_id)
                    mapdata_task.delay('collections', collection.id, 'standard', refresh=True)
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully scheduled mapdata refresh for Collection ID {entity_id}'))
                except Collection.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Collection with ID {entity_id} does not exist'))
            else:
                # Fetch all Collections
                collections = Collection.objects.all()
                for collection in collections:
                    mapdata_task.delay('collections', collection.id, 'standard', refresh=True)
                self.stdout.write(self.style.SUCCESS('Successfully scheduled mapdata refresh for all Collections'))
