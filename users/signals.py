# users.signals.py

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from whgmail.messaging import WHGmail
import requests
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=User)
def welcome_email(sender, instance, created, **kwargs):
    """Send welcome email to new user on registration w/reply-to editorial;
       separate message to admins"""
    if created or instance.email_confirmed and not instance.__class__.objects.get(pk=instance.pk).email_confirmed:
              
        WHGmail(context={
            'template': 'welcome',
            'subject': 'Welcome to WHG',
            'to_email': instance.email,
            'greeting_name': instance.display_name,
            'username': instance.username,
            'name': instance.name,
        })
