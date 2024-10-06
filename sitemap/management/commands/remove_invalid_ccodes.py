import re
from django.core.management.base import BaseCommand

from sitemap.models import Toponym


class Command(BaseCommand):
    help = "Remove invalid entries from ccodes arrays in toponyms"

    def handle(self, *args, **kwargs):
        # Regular expression to match valid two-letter country codes (A-Z)
        valid_ccode_pattern = re.compile(r'^[A-Z]{2}$')
        updated_count = 0

        # Fetch all Toponym instances
        toponyms = Toponym.objects.all()

        for toponym in toponyms:
            if toponym.ccodes:
                # Filter out invalid ccodes (not matching the two-letter uppercase pattern)
                cleaned_ccodes = [code for code in toponym.ccodes if valid_ccode_pattern.match(code)]

                if cleaned_ccodes != toponym.ccodes:  # Only save if changes are made
                    toponym.ccodes = cleaned_ccodes
                    toponym.save()
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} toponyms.'))
