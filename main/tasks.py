from celery import shared_task # these are @task decorators
#from celery_progress.backend import ProgressRecorder
from django_celery_results.models import TaskResult
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.db import transaction, connection
from django.db.models import Q, Count
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


@shared_task()
def needs_tileset(category=None, id=None, pointcount_threshold=1500, geometrycount_threshold=1000, places_threshold=500):    
    try:
        if category == "datasets":
            obj = Dataset.objects.get(id=id)
        elif category == "collections":
            obj = Collection.objects.get(id=id)
    except ObjectDoesNotExist:
        return False, 0, 0

    total_coords = obj.places.aggregate(total=Sum('geoms__geom__coord'))['total'] or 0
    total_geometries = obj.places.aggregate(total=Sum('geoms'))['total'] or 0
    total_places = obj.places.count()

    return total_coords > pointcount_threshold or total_geometries > geometrycount_threshold or total_places > places_threshold, total_coords, total_geometries, total_places

@shared_task(bind=True)
def request_tileset(self, category=None, id=None):
    print(f'request_tileset() task: {category}-{id}')
    
    if not category or not id:
        raise ValueError("A category and id must both be provided.")
    else:
        response_data = send_tileset_request(category, id)
        
        if response_data and response_data.get("status") == "success":
            # create tileset record
            Tileset.objects.create(
                task_id=self.request.id,
                dataset=id if category == "datasets" else None,
                collection=id if category == "collections" else None,
            )
            # create log entry
            Log.objects.create(
                user=User.objects.get(id=1),
                dataset=id if category == "datasets" else None,
                collection=id if category == "collections" else None,
                logtype='tileset',
                note='Tileset created'
                )
            msg = f'Tileset created successfully for {category}-{id}.'
        else:
            msg = f'Tileset creation failed for {category}-{id}.'
        print(msg)
            
        # name = 'Editor'
        # email = 'karl.geog@gmail.com'
        # if category == "datasets":
        #     dataset = Dataset.objects.get(id=dataset_id)
        #     label = dataset.label
        #     obj = dataset
        # elif category == "collections":
        #     collection = Collection.objects.get(id=collection_id)
        #     label = collection.title
        #     obj = collection
        # try:
        #     tile_task_emailer.delay(
        #         self.request.id,
        #         dslabel,
        #         name,
        #         email,
        #         msg
        #         )
        # except:
        #     print('tile_task_emailer failed on tid', self.request.id)

