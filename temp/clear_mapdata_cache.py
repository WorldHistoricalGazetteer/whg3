# main/management/commands/clear_mapdata_cache.py
import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Clears the cache folder'

    def handle(self, *args, **options):
        cache_folder = settings.CACHES['LOCATION']
        try:
            for filename in os.listdir(cache_folder):
                file_path = os.path.join(cache_folder, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            self.stdout.write(self.style.SUCCESS('Cache folder cleared successfully'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to clear cache folder: {e}'))
