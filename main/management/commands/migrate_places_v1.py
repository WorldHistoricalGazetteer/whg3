import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from places.models import Place
from datasets.models import Dataset

class Command(BaseCommand):
    help = 'Migrate places from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import')
        parser.add_argument('--limit', type=int, default=None, help='The number of records to import (set to None to process all)')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        limit = kwargs['limit']

        # Fetch existing Place IDs
        existing_place_ids = set(Place.objects.values_list('id', flat=True))

        with open(csv_file, newline='') as file:
            reader = csv.DictReader(file)
            places = []
            count = 0
            total_processed = 0

            for row in reader:
                if limit is not None and count >= limit:
                    break
                # Check if the place already exists
                if int(row['id']) in existing_place_ids:
                    continue

                # Handle empty or 'NULL' values
                def convert_to_int(value):
                    if value == '' or value == '\\N':
                        return None
                    return int(value)

                def convert_to_array(value):
                    if value == '' or value == '\\N':
                        return None
                    return [int(x) for x in value.split(',')]

                attestation_year = convert_to_int(row['attestation_year'])
                review_tgn = convert_to_int(row['review_tgn'])
                review_wd = convert_to_int(row['review_wd'])
                review_whg = convert_to_int(row['review_whg'])
                minmax = convert_to_array(row['minmax'])

                print(f"attestation_year (before): {row['attestation_year']}")
                print(f"attestation_year (after): {attestation_year} of type {type(attestation_year)}")
                print(f"Full row: {row}")

                # Create Place instances
                try:
                    place = Place(
                        id=row['id'],
                        title=row['title'],
                        attestation_year=attestation_year,
                        ccodes=row['ccodes'],
                        dataset=Dataset.objects.get(label=row['dataset']),
                        fclasses=row['fclasses'],
                        flag=row['flag'],
                        idx_pub=row['idx_pub'],
                        indexed=row['indexed'],
                        minmax=minmax,
                        review_tgn=review_tgn,
                        review_wd=review_wd,
                        review_whg=review_whg,
                        src_id=row['src_id'],
                        timespans=row['timespans'],
                        create_date=row['create_date'],
                        idx_builder=row['idx_builder']
                    )
                except Exception as e:
                    print(f"Error creating Place instance for row: {row}")
                    print(f"Error: {e}")
                    continue

                places.append(place)
                count += 1

                # Print all places being created in this batch
                if len(places) == 1000:
                    print("Preparing to bulk create the following places:")
                    for p in places:
                        print(p)

                    try:
                        with transaction.atomic():
                            Place.objects.bulk_create(places, batch_size=1000)
                        self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(places)} places'))
                        total_processed += len(places)
                    except IntegrityError as e:
                        self.stderr.write(self.style.ERROR(f'Transaction failed: {e}'))
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f'Error: {e}'))
                    finally:
                        places = []

            # Import any remaining places
            if places:
                print("Preparing to bulk create the remaining places:")
                for p in places:
                    print(p)

                try:
                    with transaction.atomic():
                        Place.objects.bulk_create(places, batch_size=1000)
                    self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(places)} places'))
                    total_processed += len(places)
                except IntegrityError as e:
                    self.stderr.write(self.style.ERROR(f'Transaction failed: {e}'))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'Error: {e}'))

            self.stdout.write(self.style.SUCCESS(f'Total processed: {total_processed} places'))
