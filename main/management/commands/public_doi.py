# myapp/management/commands/public_doi.py
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from collection.models import Collection
from datasets.models import Dataset
from resources.models import Resource


class Command(BaseCommand):
    help = 'Publish DOIs for all public datasets and collections'

    def handle(self, *args, **kwargs):
        self.stdout.write('Publishing DOIs for all public datasets...')
        self.dataset_dois()

        self.stdout.write('Publishing DOIs for all public collections...')
        self.collection_dois()

        self.stdout.write('Publishing DOIs for all public resources...')
        self.resource_dois()

    def dataset_dois(self):
        datasets = Dataset.objects.all().filter(public=True)

        for dataset in datasets:
            dataset.save()
            self.stdout.write(f'DOI published for dataset {dataset.id}')

    def collection_dois(self):
        collections = Collection.objects.all().filter(public=True)

        for collection in collections:
            collection.save()
            self.stdout.write(f'DOI published for collection {collection.id}')

    def resource_dois(self):
        resources = Resource.objects.all().filter(public=True)

        for resource in resources:
            resource.save()
            self.stdout.write(f'DOI published for resource {resource.id}')