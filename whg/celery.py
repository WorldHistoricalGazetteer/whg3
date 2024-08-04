# whg/celery.py

from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from django.conf import settings
# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whg.settings")

app = Celery('whg')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.result_expires = None

# Configure broker URL explicitly if needed; otherwise, use CELERY_BROKER_URL from settings
#app.conf.broker_url = 'redis://localhost:6379'
# override Beat default daily cleanup task
app.conf.result_expires = None

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Ensure Celery uses Django's logging configuration
from logging.config import dictConfig
dictConfig(settings.LOGGING)

@app.task(bind=True)
def debug_task(self):
    logger = logging.getLogger(__name__)
    logger.info('Request: {0!r}'.format(self.request))
