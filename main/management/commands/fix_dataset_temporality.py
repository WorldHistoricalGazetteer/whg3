# main/management/commands/fix_dataset_temporality.py

'''
To be used only for datasets in which all places have only one timespan
'''

from django.core.management.base import BaseCommand
from django.db import transaction
from datasets.models import Dataset
from places.models import Place, PlaceWhen
import json

class Command(BaseCommand):
    help = 'Update places and place_when based on dataset label and default parameters'

    def handle(self, *args, **kwargs):
        dataset_label = "viabundus_10393"
        default_start = 1350
        default_end = 1650
        default_start_attestation = False
        default_end_attestation = False
        default_start_mode = 5
        default_end_mode = 5

        # Fetch the dataset creation date
        try:
            dataset = Dataset.objects.get(label=dataset_label)
            dataset_creation_year = dataset.create_date.year
        except Dataset.DoesNotExist:
            self.stdout.write(self.style.ERROR('Dataset with label %s does not exist' % dataset_label))
            return

        with transaction.atomic():
            # Fetch the places with the given dataset_label
            places_to_update = Place.objects.filter(dataset=dataset_label)

            for place in places_to_update:
                
                place_start_set = place.minmax[0] and place.minmax[0] != -99999
                place_end_set = place.minmax[1] and place.minmax[1] != 9999
                    
                place_default_start = place.attestation_year if (default_start_attestation and place.attestation_year) else default_start
                place_default_end = place.attestation_year if (default_end_attestation and place.attestation_year) else default_end
                
                place_start = place.minmax[0] if place_start_set else place_default_start
                place_end = place.minmax[1] if place_end_set else place_default_end

                # Fetch related place_when records
                place_when_records = PlaceWhen.objects.filter(place_id=place.id)

                for place_when in place_when_records:
                    # Update minmax in the place_when table
                    place_when.minmax = [place_start, place_end]

                    # Construct start object based on default_start_mode
                    if place_start_set:
                        start = {"in": place_start}
                    elif default_start_mode == 1: # from some date during the `end` (or `default_end`) year
                        start = {"in": place_end}
                    elif default_start_mode == 2: # from the start of the `end` (or `default_end`) year
                        start = {"earliest": place_end}
                    elif default_start_mode == 3: # before the start of the `end` (or `default_end`) year
                        start = {"latest": place_end}
                    elif default_start_mode == 4: # only from the `default_start` year
                        start = {"earliest": place_start}
                    elif default_start_mode == 5: # before the start of the `default_start` year
                        start = {"latest": place_start}
                    elif default_start_mode == 6: # before the year of the dataset's creation
                        start = {"latest": dataset_creation_year}
                    else:
                        start = {}

                    # Construct end object based on default_end_mode
                    if place_end_set:
                        end = {"in": place_end}
                    elif default_end_mode == 1: # until some date during the `start` (or `default_start`) year
                        end = {"in": place_start}
                    elif default_end_mode == 2: # only until the end of the `start` (or `default_start`) year
                        end = {"latest": place_start}
                    elif default_end_mode == 3: # after the end of the `start` (or `default_start`) year
                        end = {"earliest": place_start}
                    elif default_end_mode == 4: # only until the `default_end` year
                        end = {"latest": place_end}
                    elif default_end_mode == 5: # after the end of the `default_end` year
                        end = {"earliest": place_end}
                    elif default_end_mode == 6: # after the year of the dataset's creation
                        end = {"earliest": dataset_creation_year}
                    else:
                        end = {}

                    # Construct the jsonb field in the place_when table
                    jsonb_data = {
                        "minmax": [place_start, place_end],
                        "timespans": [
                            {
                                "start": start,
                                "end": end
                            }
                        ],
                        "source_year": place.attestation_year if place.attestation_year else None
                    }

                    place_when.jsonb = jsonb_data
                    place_when.save()
                
                place.minmax = [place_start, place_end]
                place.timespans = json.dumps([place.minmax])
                place.save()

        self.stdout.write(self.style.SUCCESS('Successfully updated places and place_when for dataset: %s' % dataset_label))
