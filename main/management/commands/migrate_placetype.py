import json
import itertools
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError, connection
from places.models import Place, PlaceLink

class Command(BaseCommand):
    help = 'Migrate place_link from JSONL file'

    def add_arguments(self, parser):
        parser.add_argument('jsonl_file', type=str, help='The path to the JSONL file to import')
        parser.add_argument('--limit', type=int, default=None, help='The number of records to import (set to None to process all)')
        parser.add_argument('--error_log', type=str, default='error_log.jsonl', help='The path to the error log file')

    def handle(self, *args, **kwargs):
        jsonl_file = kwargs['jsonl_file']
        limit = kwargs['limit']
        error_log = kwargs['error_log']

        problematic_rows = []
        missing_place_ids = []

        def batch_iterator(iterator, batch_size):
            """Yields batches of specified size from an iterator."""
            while True:
                batch = list(itertools.islice(iterator, batch_size))
                if not batch:
                    break
                yield batch

        def adjust_sequence():
            """Adjust the sequence to be in sync with the maximum ID in the table."""
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(id) FROM place_link;")
                max_id = cursor.fetchone()[0]
                cursor.execute("SELECT last_value FROM place_link_id_seq;")
                last_value = cursor.fetchone()[0]
                self.stdout.write(self.style.WARNING(f'Current max(id) in place_link: {max_id}'))
                self.stdout.write(self.style.WARNING(f'Current last_value in place_link_id_seq: {last_value}'))
                if max_id:
                    new_start_value = max_id + 1
                    cursor.execute(f"SELECT setval('place_link_id_seq', {new_start_value}, false);")
                    self.stdout.write(self.style.WARNING(f'Set place_link_id_seq to start from {new_start_value}'))

        with open(jsonl_file, 'r') as file:
            reader = (json.loads(line) for line in file)
            count = 0
            total_processed = 0

            self.stdout.write(self.style.WARNING('Starting migration process...'))

            for batch_index, batch in enumerate(batch_iterator(reader, 1000), start=1):
                if limit is not None and count >= limit:
                    self.stdout.write(self.style.WARNING(f'Reached limit of {limit} records. Stopping.'))
                    break

                self.stdout.write(self.style.WARNING(f'Processing batch {batch_index}...'))
                placelinks = []
                for row_index, row in enumerate(batch, start=1):
                    if limit is not None and count >= limit:
                        break

                    self.stdout.write(self.style.WARNING(f'Processing row {row_index} in batch {batch_index}: {row}'))
                    try:
                        place = Place.objects.get(id=row['place_id'])  # Check if Place exists
                        self.stdout.write(self.style.WARNING(f'Found place with id {row["place_id"]}'))
# black_parent, create_date, id, jsonb, place_id, review_note, reviewer_id, src_id, task_id
                        # Use get_or_create to avoid creating duplicates
                        placelink, created = PlaceLink.objects.get_or_create(
                            place=place,
                            src_id=row['src_id'],
                            jsonb=row['jsonb'],
                            task_id=row['task_id'],
                            reviewer_id=row.get('reviewer_id', None),
                            black_parent=row['black_parent'],
                            review_note=row['review_note'],
                            create_date=row.get('created', None),
                        )

                        if created:
                            self.stdout.write(self.style.WARNING(f'Created PlaceLink instance for row {row_index}'))
                            placelinks.append(placelink)  # Append the new PlaceLink to the list
                            count += 1
                        else:
                            self.stdout.write(self.style.WARNING(f'Skipped duplicate PlaceLink for row {row_index}'))

                        if row_index % 100 == 0:
                            self.stdout.write(self.style.WARNING(f'Processed {row_index} rows in current batch...'))

                        if limit is not None and count >= limit:
                            self.stdout.write(self.style.WARNING(f'Reached limit of {limit} records. Stopping.'))
                            break

                    except Place.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'Place with id {row["place_id"]} does not exist'))
                        missing_place_ids.append(row['place_id'])
                        problematic_rows.append({
                            'row': row,
                            'error': f'Place with id {row["place_id"]} does not exist'
                        })
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Exception for row {row_index}: {str(e)}'))
                        problematic_rows.append({
                            'row': row,
                            'error': str(e)
                        })
                        continue

                self.stdout.write(self.style.WARNING(f'PlaceLinks to create in batch {batch_index}: {len(placelinks)}'))

                if placelinks:
                    adjust_sequence()
                    # Bulk create placelinks
                    try:
                        with transaction.atomic():
                            adjust_sequence()

                            self.stdout.write(self.style.WARNING(f'Attempting to bulk create {len(placelinks)} placelinks.'))
                            PlaceLink.objects.bulk_create(placelinks, batch_size=1000)
                        self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(placelinks)} placelinks'))
                        total_processed += len(placelinks)
                        placelinks.clear()
                    except IntegrityError as e:
                        self.stdout.write(self.style.ERROR(f'IntegrityError: {str(e)}'))
                        problematic_rows.extend([{'row': r, 'error': str(e)} for r in batch])
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Exception: {str(e)}'))
                        problematic_rows.extend([{'row': r, 'error': str(e)} for r in batch])

                if limit is not None and count >= limit:
                    self.stdout.write(self.style.WARNING(f'Reached limit of {limit} records. Stopping.'))
                    break

            # Final bulk create if the loop is broken due to limit
            if placelinks:
                try:
                    with transaction.atomic():
                        adjust_sequence()

                        self.stdout.write(self.style.WARNING(f'Final bulk create {len(placelinks)} placelinks.'))
                        PlaceLink.objects.bulk_create(placelinks, batch_size=1000)
                    self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(placelinks)} placelinks'))
                    total_processed += len(placelinks)
                    placelinks.clear()
                except IntegrityError as e:
                    self.stdout.write(self.style.ERROR(f'IntegrityError: {str(e)}'))
                    problematic_rows.extend([{'row': r, 'error': str(e)} for r in batch])
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Exception: {str(e)}'))
                    problematic_rows.extend([{'row': r, 'error': str(e)} for r in batch])

            self.stdout.write(self.style.SUCCESS(f'Total processed: {total_processed} placelinks'))

            # Save problematic rows to a file
            if problematic_rows:
                with open(error_log, 'w') as error_file:
                    for problem in problematic_rows:
                        error_file.write(json.dumps(problem) + '\n')
                self.stdout.write(self.style.WARNING(f'Encountered errors with {len(problematic_rows)} rows. See {error_log} for details.'))

            # Log missing place_ids
            if missing_place_ids:
                with open('missing_place_ids.jsonl', 'w') as missing_file:
                    for place_id in missing_place_ids:
                        missing_file.write(json.dumps({'missing_place_id': place_id}) + '\n')
                self.stdout.write(self.style.WARNING(f'Encountered {len(missing_place_ids)} missing place_ids. See missing_place_ids.jsonl for details.'))

