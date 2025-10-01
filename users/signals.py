# users.signals.py

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from whgmail.messaging import WHGmail
import requests
import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger('messaging')
User = get_user_model()

@receiver(post_save, sender=User)
def welcome_email(sender, instance, created, **kwargs):
    """Send welcome email to new user on registration w/reply-to editorial;
       separate message to admins vias Slack"""
    if not created:
        return  # only act on first save (registration)

    logger.debug(f"New user created: {instance.id} | {instance.username} | {instance.name}, sending welcome email to {instance.email}")
              
    WHGmail(context={
        'template': 'welcome',
        'subject': 'Welcome to WHG',
        'to_email': instance.email,
        'greeting_name': instance.name,
        'username': instance.username,
        'name': instance.name,
    })

    try:
        slack_message = (
            f"*Subject:* New User Registered\n"
            f"*Username:* {instance.username}\n"
            f"*Name:* {instance.name}\n"
            f"*User ID:* {instance.id}\n"
            f"----------------------------------------"
        )
        client = WebClient(token=settings.SLACK_BOT_OAUTH)
        response = client.chat_postMessage(
            channel='site-notifications',
            text=slack_message
        )

        if response["ok"]:
            logger.info("Message sent to Slack.")
        else:
            logger.error(f"Failed to send message to Slack: {response['error']}")

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
    except Exception as e:
        logger.exception("Error occurred while sending Slack notification for new user registration")
