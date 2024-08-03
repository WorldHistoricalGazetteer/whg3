from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whg.settings")

app = Celery('whg')

app.config_from_object('django.conf:settings', namespace='CELERY')
#app.conf.broker_url = 'redis://localhost:6379'
app.conf.result_expires = None


# override Beat default daily cleanup task
app.conf.result_expires = None

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
