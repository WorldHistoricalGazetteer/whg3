from django.db import models, transaction
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Collection

# if public changes to True & size threshold met, create tileset
@receiver(pre_save, sender=Collection)
def handle_public_status_change(sender, instance, **kwargs):
  print('collection public signal', instance)
  from main.tasks import request_tileset
  threshold = 50
  if instance.id:  # Check if it's an existing instance, not new
    old_instance = sender.objects.get(pk=instance.pk)
    print('public old, new:', old_instance.public, instance.public)
    if old_instance.public != instance.public:  # There's a change in 'public' status
      if instance.public:
        if instance.places_all.count() > threshold:
          print('collection signal: has tileset?', instance.tilesets.count() > 0)
          # Changed from False to True, create the tileset
          tiletype = instance.vis_parameters.get('tiletype', 'normal')
          transaction.on_commit(lambda: request_tileset.delay(None, instance.id, tiletype))
        else:
          print('handle_public_status_change: no tileset created')
      # else:
      #   print('handle_public_status_change: unindex from public?', instance.public)
      #   # Changed from True to False, remove the records from the index
      #   transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))
