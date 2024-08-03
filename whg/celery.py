from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

app = Celery('whg')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.result_expires = None


# override Beat default daily cleanup task
app.conf.result_expires = None

# Load task modules from all registered Django app configs
app.autodiscover_tasks()

# Ensure Celery uses Django's logging configuration
from logging.config import dictConfig
dictConfig(settings.LOGGING)

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
