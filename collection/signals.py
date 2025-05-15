# collections.signals.py

from django.contrib.gis.geos import Polygon, MultiPolygon
from django.core.cache import caches
from django.db.models.signals import pre_delete, pre_save, post_save
from django.dispatch import receiver

from utils.doi import doi
from .models import Collection
from .utils import compute_collection_bbox


def handle_collection_bbox(sender, instance, **kwargs):
    bbox = compute_collection_bbox(instance)
    if bbox:
        instance.bbox = bbox
    else:
        instance.bbox = None


@receiver(pre_save, sender=Collection)
def check_featured_field_change(sender, instance, **kwargs):
    """
    Signal handler to detect if the 'featured' field has been changed.
    """
    if instance.pk:
        try:
            existing_instance = sender.objects.get(pk=instance.pk)
            # Check if the 'featured' field has changed
            if existing_instance.featured != instance.featured:
                caches['property_cache'].delete(f"collection:{instance.pk}:carousel_metadata")
                caches['property_cache'].delete(f"collection:{instance.pk}:citation_csl")
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender=Collection)
def handle_collection_post_save(sender, instance, created, **kwargs):
    handle_collection_bbox(sender, instance, **kwargs)
    doi(instance._meta.model_name, instance.id)


@receiver(pre_delete, sender=Collection)
def handle_collection_delete(sender, instance, **kwargs):
    doi(instance._meta.model_name, instance.id, 'hide')
