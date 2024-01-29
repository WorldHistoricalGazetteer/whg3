# users.signals.py

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils.emailing import new_emailer
User = get_user_model()

@receiver(post_save, sender=User)
def welcome_email(sender, instance, created, **kwargs):
  """   Send welcome email to new user on registration w/reply-to editorial;
        separate one to admins"""
  # print('welcome_email signal received')
  if instance.email_confirmed:
    # print('welcome_email signal received, email confirmed')
    new_emailer(
      email_type='welcome',
      subject='Welcome to WHG',
      from_email=settings.DEFAULT_FROM_EMAIL,
      reply_to=[settings.DEFAULT_FROM_EDITORIAL],
      to_email=[instance.email],
      greeting_name=instance.name if instance.name else instance.username,
      username=instance.username,
      name=instance.name
    )
    new_emailer(
      email_type='new_user',
      subject='New User Registered',
      from_email=settings.DEFAULT_FROM_EMAIL,
      to_email=settings.EMAIL_TO_ADMINS,
      name=instance.name,
      username=instance.username,
      id=instance.id
    )
