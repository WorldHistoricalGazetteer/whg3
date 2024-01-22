from django.db import models, transaction
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Dataset, DatasetFile


# if public changes to True, index to pub and create tileset
# if public changes to False, unindex from pub
@receiver(pre_save, sender=Dataset)
def handle_public_status_change(sender, instance, **kwargs):
  from .tasks import index_to_pub, unindex_from_pub
  from main.tasks import request_tileset
  threshold = 2000
  if instance.id:  # Check if it's an existing instance, not new
    old_instance = sender.objects.get(pk=instance.pk)
    print('handle_public_status_change old_instance', old_instance)

    if old_instance.public != instance.public:  # There's a change in 'public' status
      if instance.public:
        print('handle_public_status_change: index to public?', instance.public)
        # Changed from False to True, index the records
        transaction.on_commit(lambda: index_to_pub.delay(instance.id))

        if instance.places.count() > threshold:
          print('handle_public_status_change: create tileset?', instance.tileset)
          # Changed from False to True, create the tileset
          tiletype = instance.vis_parameters.get('tiletype', 'normal')
          transaction.on_commit(lambda: request_tileset.delay(instance.id, tiletype))
        else:
          print('handle_public_status_change: no tileset created', instance.tileset)
      else:
        print('handle_public_status_change: unindex from public?', instance.public)
        # Changed from True to False, remove the records from the index
        transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))


# print('in datasets.signals.py')
# @receiver(pre_save, sender=Dataset)
# def create_tileset(sender, instance, **kwargs):
#   from main.tasks import request_tileset
#   threshold = 2000
#   if instance.id:  # Check if it's an existing instance, not new
#     old_instance = sender.objects.get(pk=instance.pk)
#     print('create_tileset old_instance', old_instance)
#     if old_instance.tileset != instance.tileset:  # There's a change in 'tileset' status
#       if instance.tileset and instance.places.count() > threshold:
#         print('create_tileset()...sending request', instance.tileset)
#         # Changed from False to True, create the tileset
#         transaction.on_commit(lambda: request_tileset.delay(instance.id))
#
# @receiver(pre_save, sender=Dataset)
# def toggle_public_status(sender, instance, **kwargs):
#   from .tasks import index_to_pub, unindex_from_pub
#   # If 'public' is being toggled
#   if instance.id:  # Check if it's an existing instance, not new
#     old_instance = sender.objects.get(pk=instance.pk)
#     print('toggler old_instance', old_instance)
#
#     if old_instance.public != instance.public:  # There's a change in 'public' status
#       if instance.public:
#         print('toggler: index to public?', instance.public)
#         # Changed from False to True, index the records
#         transaction.on_commit(lambda: index_to_pub.delay(instance.id))
#       else:
#         print('toggler: unindex to public?', instance.public)
#         # Changed from True to False, remove the records from the index
#         transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))

@receiver(pre_delete, sender=Dataset)
def remove_files(**kwargs):
  print('pre_delete remove_files()', kwargs)
  ds_instance = kwargs.get('instance')
  files = DatasetFile.objects.filter(dataset_id_id=ds_instance.id)
  files.delete()
