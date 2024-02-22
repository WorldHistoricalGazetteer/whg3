from celery import shared_task # these are @task decorators
#from celery_progress.backend import ProgressRecorder
from django_celery_results.models import TaskResult
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.db import transaction, connection
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
User = get_user_model()
from collection.models import Collection
from datasets.models import Dataset
from main.models import Log, Tileset
from main.views import send_tileset_request
import time

@shared_task()
def calculate_geometry_complexity(dataset_id):
    from datasets.models import Dataset

    dataset = Dataset.objects.get(id=dataset_id)
    complexity = dataset.coordinates_count

    return complexity

@shared_task(bind=True)
def request_tileset(self, dataset_id=None, collection_id=None, tiletype='normal'):
    print('request_tileset() task: dataset_id, collection_id, tiletype', dataset_id, collection_id, tiletype)
    response_data = send_tileset_request(dataset_id, collection_id, tiletype)
    if dataset_id:
      dataset = Dataset.objects.get(id=dataset_id)
      label = dataset.label
      obj = dataset
      category = 'dataset'
    elif collection_id:
      collection = Collection.objects.get(id=collection_id)
      label = collection.title
      obj = collection
      category = 'collection'
    else:
      raise ValueError('request_tileset() requires either a dataset_id or collection_id')
    name = 'Editor'
    email = 'karl.geog@gmail.com'
    if response_data and response_data.get("status") == "success":
      # create tileset record
      Tileset.objects.create(
        tiletype=tiletype,
        task_id=self.request.id,
        dataset=dataset if dataset_id else None,
        collection=collection if collection_id else None
      )
      # create log entry
      Log.objects.create(
        user=User.objects.get(id=1),
        dataset=dataset if dataset_id else None,
        collection=collection if collection_id else None,
        logtype='tileset',
        note='Tileset created',
        subtype=tiletype
      )
      print(f'Tileset created successfully for {category} ' + str(obj.id))
      msg = f'Tileset created successfully for {category} ' + str(obj.id)
    else:
      msg = 'Tileset creation failed for collection ' + str(obj.id)
    # try:
    #   tile_task_emailer.delay(
    #     self.request.id,
    #     dslabel,
    #     name,
    #     email,
    #     msg
    #   )
    # except:
    #   print('tile_task_emailer failed on tid', self.request.id)

