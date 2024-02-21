# datasets.signals.py
# when created; when public; when indexed

from django.conf import settings
from django.db import transaction
from django.db.models.signals import pre_delete, pre_save, post_save
from django.dispatch import receiver

from .models import Dataset, DatasetFile
from utils.emailing import new_emailer

import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Dataset)
def send_new_dataset_email(sender, instance, **kwargs):
  if instance.pk:  # if instance exists
    old_instance = Dataset.objects.get(pk=instance.pk)
    if old_instance.ds_status != instance.ds_status and instance.ds_status == 'uploaded':
      try:
        if not instance.owner.groups.filter(name='whg_team').exists():
          new_emailer(
            email_type='new_dataset',
            subject='New Dataset Created',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=settings.EMAIL_TO_ADMINS,
            name=instance.owner.first_name + ' ' + instance.owner.last_name,
            username=instance.owner.username,
            dataset_title=instance.title,
            dataset_label=instance.label,
            dataset_id=instance.id
          )
      except Exception as e:
        logger.exception("Error occurred while sending new dataset email")


@receiver(pre_save, sender=Dataset)
def handle_public_flag(sender, instance, **kwargs):
  # print('\nhandle_public_flag: public?', instance.public)
  from .tasks import index_to_pub, unindex_from_pub
  from main.tasks import request_tileset
  threshold = 2000
  if instance.id:  # Check if it's an existing instance, not new
    old_instance = sender.objects.get(pk=instance.pk)
    if old_instance.public != instance.public:  # There's a change in 'public' status
      # print('handle_public_flag: changed', old_instance.public, instance.public)
      # notify the owner
      owner = instance.owner
      if instance.public:
        new_emailer(
          email_type='dataset_published',
          subject='Your WHG dataset has been published',
          from_email=settings.DEFAULT_FROM_EMAIL,
          to_email=[owner.email],
          reply_to=[settings.DEFAULT_FROM_EDITORIAL],
          name=owner.name,
          greeting_name=owner.name if owner.name else owner.username,
          dataset_title=instance.title,
          dataset_label=instance.label,
          dataset_id=instance.id
        )

        # Changed from False to True, index the records
        transaction.on_commit(lambda: index_to_pub.delay(instance.id))

        # Changed from False to True, create a tileset
        if instance.places.count() > threshold:
          print('handle_public_status_change: has tileset?', instance.tilesets.count() > 0)
          tiletype = instance.vis_parameters.get('tiletype', 'normal')
          transaction.on_commit(lambda: request_tileset.delay(instance.id, tiletype))
        else:
          print('handle_public_status_change: no tileset created')
      else:
        print('handle_public_status_change: unindex from public?', instance.public)
        # Changed from True to False, remove the records from the index
        transaction.on_commit(lambda: unindex_from_pub.delay(instance.id))
        # notify the owner
        owner = instance.owner
        new_emailer(
          email_type='dataset_unpublished',
          subject='Your WHG dataset has been unpublished',
          from_email=settings.DEFAULT_FROM_EMAIL,
          to_email=[owner.email],
          reply_to=[settings.DEFAULT_FROM_EDITORIAL],
          name=owner.name,
          greeting_name=owner.name if owner.name else owner.username,
          dataset_title=instance.title,
          dataset_label=instance.label,
          dataset_id=instance.id
        )


# notify the owner when status changes to 'wd-complete' or 'indexed'
@receiver(pre_save, sender=Dataset)
def handle_status_change(sender, instance, **kwargs):
  # print('\n\nhandle_status_change: status, is public?:', instance.ds_status, instance.public)
  try:
    if instance.pk is not None:  # Check if it's an existing instance, not new
      old_instance = sender.objects.get(pk=instance.pk)
      # Check whether 'ds_status' has been changed to 'wd-complete'
      # and notify the owner, bcc to editorial
      if old_instance.ds_status != instance.ds_status and instance.ds_status == 'wd-complete':
        # print('handle_status_change: ds_status changed to wd-complete')
        owner = instance.owner
        new_emailer(
          email_type='wikidata_review_complete',
          subject='WHG reconciliation review complete',
          from_email=settings.DEFAULT_FROM_EMAIL,
          to_email=[settings.EMAIL_TO_ADMINS],
          reply_to=[settings.DEFAULT_FROM_EDITORIAL],
          bcc=[settings.DEFAULT_FROM_EDITORIAL],
          name=owner.name,
          greeting_name=owner.name if owner.name else owner.username,
          dataset_title=instance.title,
          dataset_label=instance.label,
          dataset_id=instance.id,
          editorial=settings.DEFAULT_FROM_EDITORIAL
        )
      # Check whether 'ds_status' has been changed to 'indexed'
      if old_instance.ds_status != instance.ds_status and instance.ds_status == 'indexed':
        # print('handle_status_change: ds_status changed to indexed')
        owner = instance.owner
        new_emailer(
          email_type='dataset_indexed',
          subject='Your WHG dataset is fully indexed',
          from_email=settings.DEFAULT_FROM_EMAIL,
          to_email=[owner.email],
          reply_to=[settings.DEFAULT_FROM_EDITORIAL],
          bcc=[settings.DEFAULT_FROM_EDITORIAL],
          name=owner.name,
          greeting_name=owner.name if owner.name else owner.username,
          dataset_title=instance.title,
          dataset_label=instance.label,
          dataset_id=instance.id
        )
  except Exception as e:
    print('send_dataset_email error:', e)
    logger.exception("Error occurred while sending dataset email")


@receiver(pre_delete, sender=Dataset)
def remove_files(**kwargs):
  print('pre_delete remove_files()', kwargs)
  ds_instance = kwargs.get('instance')
  files = DatasetFile.objects.filter(dataset_id_id=ds_instance.id)
  files.delete()
