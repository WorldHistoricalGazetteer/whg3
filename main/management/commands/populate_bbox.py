from django.core.management.base import BaseCommand
from datasets.models import Dataset
from datasets.signals import handle_dataset_bbox
from collection.models import Collection
from collection.signals import handle_collection_bbox

class Command(BaseCommand):
    help = 'Update bbox for datasets and collections missing it'

    def handle(self, *args, **options):
        updated_datasets = self.update_datasets()
        updated_collections = self.update_collections()

        self.stdout.write(self.style.SUCCESS(
            f"Updated {updated_datasets} datasets and {updated_collections} collections with new bbox values."
        ))

    def update_datasets(self):
        missing_bbox = Dataset.objects.filter(bbox__isnull=True)
        total = missing_bbox.count()
        self.stdout.write(f"Found {total} datasets without a bbox...")

        updated = 0
        for ds in missing_bbox:
            handle_dataset_bbox(Dataset, ds)
            if ds.bbox:
                ds.save(update_fields=['bbox'])
                self.stdout.write(f"✓ Dataset {ds.title} updated")
                updated += 1
        return updated

    def update_collections(self):
        missing_bbox = Collection.objects.filter(bbox__isnull=True)
        total = missing_bbox.count()
        self.stdout.write(f"Found {total} collections without a bbox...")

        updated = 0
        for coll in missing_bbox:
            handle_collection_bbox(Collection, coll)
            if coll.bbox:
                coll.save(update_fields=['bbox'])
                self.stdout.write(f"✓ Collection {coll.title} updated")
                updated += 1
        return updated
