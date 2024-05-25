import csv
import os
import json
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from places.models import Place
from datasets.models import Dataset
import itertools

class Command(BaseCommand):
    help = 'Migrate places from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import')
        parser.add_argument('--limit', type=int, default=None, help='The number of records to import (set to None to process all)')
        parser.add_argument('--error_log', type=str, default='error_log.csv', help='The path to the error log file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        limit = kwargs['limit']
        error_log = kwargs['error_log']

        # Fetch existing Place IDs in bulk
        self.stdout.write(self.style.WARNING('Fetching existing Place IDs...'))
        existing_place_ids = set(Place.objects.values_list('id', flat=True))
        self.stdout.write(self.style.SUCCESS(f'Fetched {len(existing_place_ids)} existing Place IDs'))

        problematic_rows = []

        def batch_iterator(iterator, batch_size):
            """Yields batches of specified size from an iterator."""
            while True:
                batch = list(itertools.islice(iterator, batch_size))
                if not batch:
                    break
                yield batch

        def convert_to_int(value):
            if value in ('', '\\N', 'NULL', None):
                return None
            return int(value)

        def convert_to_array(value):
            if value in ('', '\\N', 'NULL', None):
                return None
            try:
                # Convert from PostgreSQL array literal format
                return [int(x) for x in value.strip('{}').split(',')]
            except ValueError as e:
                print(f"ValueError: {e} for value: {value}")
                return None

        def convert_to_json(value):
            if value in ('', '\\N', 'NULL', None):
                return None
            try:
                # Ensure the JSON string is properly formatted
                return json.loads(value.replace("'", '"'))
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e} for value: {value}")
                return None

        with open(csv_file, newline='') as file:
            reader = csv.DictReader(file)
            count = 0
            total_processed = 0

            for batch in batch_iterator(reader, 1000):
                places = []
                for row in batch:
                    if limit is not None and count >= limit:
                        break
                    # Check if the place already exists
                    if int(row['id']) in existing_place_ids:
                        continue

                    attestation_year = convert_to_int(row['attestation_year'])
                    review_tgn = convert_to_int(row['review_tgn'])
                    review_wd = convert_to_int(row['review_wd'])
                    review_whg = convert_to_int(row['review_whg'])
                    minmax = convert_to_array(row['minmax'])
                    timespans = convert_to_json(row['timespans'])

                    try:
                        place = Place(
                            id=row['id'],
                            title=row['title'],
                            attestation_year=attestation_year,
                            ccodes=row['ccodes'],
                            dataset=Dataset.objects.get(label=row['dataset']),
                            fclasses=convert_to_array(row['fclasses']),
                            flag=row['flag'],
                            idx_pub=row['idx_pub'],
                            indexed=row['indexed'],
                            minmax=minmax,
                            review_tgn=review_tgn,
                            review_wd=review_wd,
                            review_whg=review_whg,
                            src_id=row['src_id'],
                            timespans=timespans,
                            create_date=row['create_date'],
                            idx_builder=row['idx_builder']
                        )
                        places.append(place)
                        count += 1

                    except Exception as e:
                        print(f"Error creating Place instance for row ID {row['id']}: {e}")
                        problematic_rows.append(row)
                        continue

                if not places:
                    continue

                # Bulk create places
                try:
                    with transaction.atomic():
                        Place.objects.bulk_create(places, batch_size=1000)
                    self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(places)} places'))
                    total_processed += len(places)
                except IntegrityError as e:
                    self.stderr.write(self.style.ERROR(f'Transaction failed: {e}'))
                    problematic_rows.extend(batch)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'Error: {e}'))
                    problematic_rows.extend(batch)

            self.stdout.write(self.style.SUCCESS(f'Total processed: {total_processed} places'))

            # Save problematic rows to a file
            if problematic_rows:
                with open(error_log, 'w', newline='') as error_file:
                    writer = csv.DictWriter(error_file, fieldnames=reader.fieldnames)
                    writer.writeheader()
                    writer.writerows(problematic_rows)
                self.stdout.write(self.style.WARNING(f'Encountered errors with {len(problematic_rows)} rows. See {error_log} for details.'))

