from django.db import models, transaction
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Collection

# if public changes to True & size threshold met, create tileset
@receiver(pre_save, sender=Collection)
def handle_public_status_change(sender, instance, **kwargs):
  from main.tasks import needs_tileset, request_tileset
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
          transaction.on_commit(lambda: request_tileset.delay(category='collections', id=instance.id))
        else:
          print('handle_public_status_change: no tileset created')
      # else:
      #   print('handle_public_status_change: unindex from public?', instance.public)
      #   # Changed from True to False, remove the records from the index
      #   transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))
