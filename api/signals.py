from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from api.download_lpf import invalidate_and_rebuild_lpf_cache, LPFCache
from collection.models import Collection
from datasets.models import Dataset

@receiver(post_save, sender=Dataset)
def dataset_lpf_saved(sender, instance, **kwargs):
    invalidate_and_rebuild_lpf_cache("dataset", instance.id)

@receiver(post_delete, sender=Dataset)
def dataset_lpf_deleted(sender, instance, **kwargs):
    LPFCache.delete_cache("dataset", instance.id)
    LPFCache.cancel_current_build("dataset", instance.id)

@receiver(post_save, sender=Collection)
def collection_lpf_saved(sender, instance, **kwargs):
    if instance.collection_class == "place":
        invalidate_and_rebuild_lpf_cache("collection", instance.id)

@receiver(post_delete, sender=Collection)
def collection_lpf_deleted(sender, instance, **kwargs):
    if instance.collection_class == "place":
        LPFCache.delete_cache("collection", instance.id)
        LPFCache.cancel_current_build("collection", instance.id)

@receiver(m2m_changed, sender=Collection.places.through)
def collection_places_changed(sender, instance, action, pk_set, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"] and instance.collection_class == "place":
        invalidate_and_rebuild_lpf_cache("collection", instance.id)  # This throttles multiple rapid changes internally
