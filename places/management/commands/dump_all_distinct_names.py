# dump_all_distinct_names.py
from django.core.management.base import BaseCommand
from places.models import PlaceName
import os
import zipfile
# from datetime import datetime (not yet)


class Command(BaseCommand):
  help = 'Generates a dump of all distinct names.'

  def add_arguments(self, parser):
    parser.add_argument('--output', type=str, help='Output file path')

  def handle(self, *args, **options):
    # Generate a default filename if none is provided
    output_file_path = options['output'] if options['output'] else self.get_default_filename()

    self.generate_dump(output_file_path)

  def get_default_filename(self):
    return os.path.join('data_dumps', 'all_distinct_names_latest.zip')

  def generate_dump(self, output_file_path):
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Fetch distinct toponyms
    distinct_toponyms = PlaceName.objects.values_list('toponym', flat=True).distinct()

    # Writing to a .txt file inside a .zip archive
    with zipfile.ZipFile(output_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
      with zipf.open('distinct_toponyms.txt', 'w') as temp_file:
        for toponym in distinct_toponyms:
          temp_file.write(f"{toponym}\n".encode('utf-8'))

    self.stdout.write(self.style.SUCCESS(f'Successfully generated distinct toponyms dump at {output_file_path}'))
