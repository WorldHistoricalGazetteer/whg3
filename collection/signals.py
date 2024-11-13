# collections.signals.py
from functools import reduce

from django.contrib.gis.geos import Polygon, MultiPolygon
from django.db import models, transaction
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Collection
from utils.mapdata import mapdata_task

@receiver(pre_save, sender=Collection)
def handle_collection_bbox(sender, instance, **kwargs):
    if instance.collection_class == "place":
        # Collect bounding boxes from places and convert them to Polygons
        bboxes = [
            Polygon.from_bbox(place.extent) for place in instance.places.all() if place.extent
        ]
    else:  # collection_class == "dataset"
        # Collect bounding boxes from datasets and convert them to Polygons
        bboxes = [dataset.bbox for dataset in instance.datasets.all() if dataset.bbox]

    if bboxes:
        # Combine all bounding boxes into a MultiPolygon
        combined_bbox = MultiPolygon(bboxes)
        instance.bbox = Polygon.from_bbox(combined_bbox.extent)

    else:
        instance.bbox = None


# if public changes to True & size threshold met, create tileset
@receiver(pre_save, sender=Collection)
def handle_public_status_change(sender, instance, **kwargs):
    from main.tasks import needs_tileset, process_tileset_request
    print('collection public signal', instance)
    threshold = 50
    if instance.id:  # Check if it's an existing instance, not new
        old_instance = sender.objects.get(pk=instance.pk)
        print('public old, new:', old_instance.public, instance.public)

        if old_instance.public != instance.public:  # There's a change in 'public' status
            if instance.public:

                object_needs_tileset, _, _, _ = needs_tileset('collections', instance.id)

                if object_needs_tileset:
                    # Changed from False to True, create the tileset
                    transaction.on_commit(lambda: process_tileset_request.delay('collections', instance.id, 'generate'))
                else:
                    print('handle_public_status_change: no tileset created')
                    if old_instance.rel_keywords != instance.rel_keywords:
                        print('handle_public_status_change: rel_keywords changed')
                        transaction.on_commit(
                            lambda: mapdata_task.delay('collections', instance.id, 'standard', refresh=True))
            # else:
            #   print('handle_public_status_change: unindex from public?', instance.public)
            #   # Changed from True to False, remove the records from the index
            #   transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))
        else:
            if old_instance.rel_keywords != instance.rel_keywords:
                transaction.on_commit(lambda: mapdata_task.delay('collections', instance.id, 'standard', refresh=True))
