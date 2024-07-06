# main/management/commands/refresh_mapdata_cache.py

from django.core.management.base import BaseCommand
from collection.models import Collection
from datasets.models import Dataset
from utils.mapdata import mapdata_task

class Command(BaseCommand):
    help = 'Refresh mapdata for all Datasets and Collections'

    def handle(self, *args, **options):
        # Fetch all Datasets excluding those with core=True
        datasets = Dataset.objects.filter(core=False)
        for dataset in datasets:
            mapdata_task.delay('datasets', dataset.id, 'standard', refresh=True)

        # Fetch all Collections
        collections = Collection.objects.all()
        for collection in collections:
            mapdata_task.delay('collections', collection.id, 'standard', refresh=True)

        self.stdout.write(self.style.SUCCESS('Successfully scheduled mapdata refresh for all Datasets and Collections'))
