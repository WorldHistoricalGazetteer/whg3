import json

from django.core.management.base import BaseCommand

from datasets.models import Dataset
from places.models import PlaceGeom

SPECIAL_PIDS = {
    6691746, 6691747, 6691749, 6691750, 6691753, 6691754, 6691758, 6691766, 6691769,
    6691779, 6691780, 6691786, 6691787, 6691794, 6691801, 6691802, 6691809, 6691817,
    6691830, 6691831, 6691845, 6691846, 6691848, 6691849, 6691855, 6691856, 6691858,
    6691859, 6691862, 6691863, 6691866, 6691867, 6691869, 6691872, 6691876, 6691880,
    6691887, 6691897, 6691904, 6691905, 6691916, 6691922, 6691923, 6691930, 6691937,
    6691940, 6691941, 6691953, 6691958, 6691959, 6691962, 6691984, 6691986, 6691987,
    6691993, 6691997, 6692001, 6692017, 6692023, 6692024, 6692032, 6692034, 6692048,
    6692051, 6692058, 6692068, 6692072, 6692073, 6692088, 6692101, 6692102, 6692149,
    6692121, 6692123, 6692124, 6692125, 6692126, 6692130, 6692133, 6692134, 6692135,
    6692138, 6692139, 6692142, 6692146, 6692157, 6692168, 6692170, 6692171, 6692178,
    6692180, 6692183, 6692190, 6692198, 6692202, 6692203, 6692210, 6692247, 6692216,
    6692219, 6692220, 6692225, 6692229, 6692240, 6692253, 6692258, 6692259, 6692269,
    6692270, 6692275, 6692281, 6692283, 6692285, 6692298, 6692304, 6692307, 6692313,
    6692315, 6692321, 6692324, 6692325, 6692331, 6692333, 6692334, 6692335, 6692338,
    6692351, 6692366, 6692368, 6692369, 6692372, 6692373, 6692375, 6692377, 6692378,
    6692379, 6692382, 6692395, 6692400, 6692407, 6692408, 6692417, 6692431, 6692433,
    6692434, 6692435, 6692436, 6692453, 6692458, 6692459, 6692461, 6692463, 6692474,
    6692475, 6692482, 6692483, 6692484, 6692485, 6692487, 6692491, 6692493, 6692497,
    6692498,
}

class Command(BaseCommand):
    help = "Reprocess PlaceGeoms for Dataset 838: convert `granularity` to `approximation`"

    def handle(self, *args, **options):
        DATASET_ID = 838

        try:
            dataset = Dataset.objects.get(id=DATASET_ID)
            dataset_label = dataset.label
            print(f"Found dataset label: {dataset_label}")
        except Dataset.DoesNotExist:
            print(f"No dataset found with id {DATASET_ID}")
            exit(1)

        placegeoms = PlaceGeom.objects.filter(place__dataset=dataset_label)

        self.stdout.write(f"Found {placegeoms.count()} PlaceGeoms for dataset {DATASET_ID} ({dataset_label})")
        updated_count = 0

        for pg in placegeoms:
            geom_data = pg.jsonb
            if not geom_data:
                continue

            geom_type = geom_data.get('type')
            # self.stdout.write(f"Checking PlaceGeom id={pg.id}, Place id={pg.place.id}, type={geom_type}")
            if geom_type in ('Point', 'MultiPoint'):
                # self.stdout.write(f"  Skipping because it is a {geom_type}")
                continue

            pid = pg.place.id
            tolerance = 30 if pid in SPECIAL_PIDS else 5
            approximation_obj = {
                "type": "gvp:approximateLocation",
                "tolerance": tolerance
            }

            updated = False

            if geom_type == 'GeometryCollection':
                self.stdout.write(
                    f"  It's a GeometryCollection with {len(geom_data.get('geometries', []))} subgeometries")
                for geometry in geom_data.get('geometries', []):
                    self.stdout.write(f"    Processing subgeometry type={geometry.get('type')}")
                    geometry["approximation"] = approximation_obj
                    geometry.pop("granularity", None)
                    updated = True
            else:
                # Single geometry
                geom_data["approximation"] = approximation_obj
                geom_data.pop("granularity", None)
                updated = True

            if updated:
                pg.jsonb = geom_data
                pg.save()
                updated_count += 1
                self.stdout.write(f"Updated PlaceGeom id={pg.id}, Place pid={pid}")

        self.stdout.write(self.style.SUCCESS(f"Finished. {updated_count} PlaceGeoms updated."))
