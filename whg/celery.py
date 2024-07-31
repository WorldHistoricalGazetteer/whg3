from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whg.settings")

app = Celery('whg')

# Load configuration from Django settings with the CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure broker URL explicitly if needed; otherwise, use CELERY_BROKER_URL from settings
app.conf.broker_url = 'redis://localhost:6379'

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))