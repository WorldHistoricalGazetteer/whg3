# resources/signals.py

from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver

from utils.doi import doi
from .models import Resource

import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Resource)
def pre_save_resource(sender, instance, **kwargs):
    logger.info(f"About to save Resource: {instance.title}")


@receiver(post_save, sender=Resource)
def post_save_resource(sender, instance, created, **kwargs):
    doi(instance._meta.model_name, instance.id)

    if created:
        logger.info(f"New Resource created: {instance.title}")
    else:
        logger.info(f"Resource updated: {instance.title}")


@receiver(pre_delete, sender=Resource)
def pre_delete_resource(sender, instance, **kwargs):
    logger.info(f"About to delete Resource: {instance.title}")
    doi(instance._meta.model_name, instance.id, 'hide')