# ingestion/management/commands/load_dataset_configs.py
from django.conf import settings
from django.core.management.base import BaseCommand
from ingestion.models import DatasetConfig

class Command(BaseCommand):
    help = 'Load initial dataset configurations into the database'

    def handle(self, *args, **kwargs):
        configs = settings.REMOTE_DATASET_CONFIGS

        for config in configs:
            DatasetConfig.objects.update_or_create(
                dataset_name=config['dataset_name'],
                defaults={
                    'url': config['url'],
                    'item_path': config['item_path'],
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully loaded dataset configurations.'))
