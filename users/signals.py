# users.signals.py

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils.emailing import new_emailer

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    if created:
        new_emailer(
            email_type='welcome',
            subject='Welcome to WHG',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=[instance.email],
            name=instance.username
        )
        new_emailer(
            email_type='new_user',
            subject='New User Registered',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=settings.EMAIL_TO_ADMINS,
            name=instance.username,
            id=instance.id
        )