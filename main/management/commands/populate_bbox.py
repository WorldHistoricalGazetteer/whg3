# myapp/management/commands/populate_bbox.py
from django.core.management.base import BaseCommand
from django.db.models.signals import pre_save

from collection.models import Collection
from datasets.models import Dataset

class Command(BaseCommand):
    help = 'Pre-populate bbox fields for all datasets and collections'

    def handle(self, *args, **kwargs):
        # Pre-populate bbox for all datasets
        # self.stdout.write('Populating bbox fields for all datasets...')
        # self.populate_dataset_bbox()

        # Pre-populate bbox for all collections
        self.stdout.write('Populating bbox fields for all collections...')
        self.populate_collection_bbox()

    def populate_dataset_bbox(self):
        datasets = Dataset.objects.all()

        for dataset in datasets:
            pre_save.send(sender=Dataset, instance=dataset)
            dataset.save(update_fields=['bbox'])
            self.stdout.write(f'BBox populated for dataset {dataset.id}')

    def populate_collection_bbox(self):
        collections = Collection.objects.all()

        for collection in collections:
            pre_save.send(sender=Collection, instance=collection)
            collection.save(update_fields=['bbox'])
            self.stdout.write(f'BBox populated for collection {collection.id}')
