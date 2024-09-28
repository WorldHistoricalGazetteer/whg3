# find/tasks.py

from celery import shared_task
from django.core import management

@shared_task
def regenerate_sitemap():
    management.call_command('refresh_sitemap')
