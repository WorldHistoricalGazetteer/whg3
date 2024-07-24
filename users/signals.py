# users.signals.py

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils.emailing import new_emailer
import requests
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=User)
def welcome_email(sender, instance, created, **kwargs):
    """Send welcome email to new user on registration w/reply-to editorial;
       separate message to admins"""
    if created or instance.email_confirmed and not instance.__class__.objects.get(pk=instance.pk).email_confirmed:
        try:
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
        except Exception as e:
            print('Error occurred while sending welcome email to new user', e)
            logger.exception("Error occurred while sending welcome email to new user")

        try:
            slack_message = (
                f"*Subject:* New User Registered\n"
                f"*Username:* {instance.username}\n"
                f"*Name:* {instance.name}\n"
                f"*User ID:* {instance.id}\n"
                f"----------------------------------------"
            )
            response = requests.post(settings.SLACK_NOTIFICATION_WEBHOOK, json={"text": slack_message})
            if response.status_code == 200:
                print("Message sent to Slack.")
            else:
                print(f"Failed to send message to Slack: {response.status_code}, {response.text}")
        except Exception as e:
            print('Error occurred while sending Slack notification for new user registration', e)
            logger.exception("Error occurred while sending Slack notification for new user registration")
