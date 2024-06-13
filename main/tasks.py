
# Implement distributed lock to enqueue tileset generation requests
import redis
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)  # Use the service name from Docker Compose for the host
from redis.exceptions import WatchError

from celery import shared_task
from celery.result import AsyncResult
#from celery_progress.backend import ProgressRecorder
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.db import transaction, connection
from django.db.models import Sum, Count, Subquery, OuterRef # import Q, Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
User = get_user_model()
from collection.models import Collection
from datasets.models import Dataset
from main.models import Log, Tileset
from places.models import PlaceGeom
from utils.mapdata import mapdata, mapdata_task, reset_standard_mapdata
import json
import requests
import time
from urllib.parse import urlparse

@shared_task()
def calculate_geometry_complexity(dataset_id):
    from datasets.models import Dataset

    dataset = Dataset.objects.get(id=dataset_id)
    complexity = dataset.coordinates_count

    return complexity

@shared_task()
def needs_tileset(category=None, id=None, pointcount_threshold=5000, geometrycount_threshold=10000, places_threshold=1000):
    try:
        if category == "datasets":
            obj = Dataset.objects.get(id=id)
        elif category == "collections":
            obj = Collection.objects.get(id=id)
    except ObjectDoesNotExist:
        return -1, 0, 0, 0
    
    # Check if all geometries are null
    if not obj.places.filter(geoms__isnull=False).exists():
        return -2, 0, 0, 0

    total_places = obj.places.count()

    if total_places > places_threshold:
        return True, -1, -1, total_places

    # Check if the total geometries exceed the threshold, if so, exit early
    annotated_places = obj.places.annotate(total_geometries=Count('geoms'))
    total_geometries = annotated_places.aggregate(total_geometries_count=Sum('total_geometries'))['total_geometries_count'] or 0
    if total_geometries > geometrycount_threshold:
        return True, -1, total_geometries, total_places

    # Calculate the total sum of coordinates
    total_coords = sum(
        place_geom.geom.num_coords for place in obj.places.all() 
        for place_geom in place.geoms.all() if place_geom.geom is not None
    ) or 0
    
    return total_coords > pointcount_threshold, total_coords, total_geometries, total_places

@shared_task()
def process_tileset_request(category, id, action):
    redis_client.set(f'{category}-{id}-{action}', 'pending', ex=3600)
    print(f"Processing tileset request: {category}-{id}-{action}")
    if not category or not id:
        redis_client.set(f'{category}-{id}-{action}', 'failed', ex=3600)
        raise ValueError("A category and id must both be provided.")
    else:
        
        response_data = send_tileset_request(category, id, action)
        
        if response_data and response_data.get("status") == "success":
            redis_client.set(f'{category}-{id}-{action}', 'success', ex=3600)

            # Retrieve Dataset instance if category is "datasets"
            try:
                dataset_instance = Dataset.objects.get(id=id) if category == "datasets" else None
            except ObjectDoesNotExist:
                dataset_instance = None
            
            # Retrieve Collection instance if category is "collections"
            try:
                collection_instance = Collection.objects.get(id=id) if category == "collections" else None
            except ObjectDoesNotExist:
                collection_instance = None              
            
            # create tileset record
            Tileset.objects.create(
                task_id=process_tileset_request.request.id,
                dataset=dataset_instance,
                collection=collection_instance,
            )
            # create log entry
            Log.objects.create(
                user=User.objects.get(id=1),
                dataset=dataset_instance,
                collection=collection_instance,
                logtype='tileset',
                note=f'Tileset {"created" if action == "generate" else "deleted"}'
                )
            msg = f'Tileset {"created" if action == "generate" else "deleted"} successfully for {category}-{id}.'
            print(msg)
            
            # After completing the current request, recursively call process_tileset_request to handle any further queued requests
            process_next_tileset_request()
            
            return {'success': True, 'message': msg}
        else:
            redis_client.set(f'{category}-{id}-{action}', 'failed', ex=3600)
            msg = f'Tileset {"creation" if action == "generate" else "deletion"} failed for {category}-{id}.'
            print(msg)
            return {'success': False, 'message': msg}

def process_next_tileset_request():
    # Dequeue the next tileset request from tileset_queue and process it
    queued_request = redis_client.lpop('tileset_queue')
    if queued_request:
        queued_category, queued_id, queued_action = queued_request.decode('utf-8').split('-')
        print(f'Dequeuing and processing queued request: {queued_category}-{queued_id}-{queued_action}')
        process_tileset_request.delay(queued_category, queued_id, queued_action)

@shared_task()
def request_tileset(category, id, action):
    print(f'request_tileset() task: {category}-{id}')

    # Acquire distributed lock
    acquired_lock = redis_client.set(f'request_tileset_lock', 'locked', nx=True, ex=300)
    print(f'acquired_lock: {category}-{id}-{action}', acquired_lock)

    if not acquired_lock:
        print('Another instance of request_tileset() is already running. Queueing request.')
        redis_client.set(f'{category}-{id}-{action}', 'queued', ex=3600)
        # Enqueue the request if the lock is already acquired
        with redis_client.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(f'request_tileset_lock')
                    pipe.multi()
                    pipe.rpush('tileset_queue', f'{category}-{id}-{action}')
                    pipe.execute()
                    break
                except redis.WatchError:
                    continue
        return {'success': False, 'message': 'Request queued due to lock.'}

    try:
        # Process the current request
        process_tileset_request.delay(category, id, action)
        
    finally:
        redis_client.delete(f'request_tileset_lock')
    
def send_tileset_request(category=None, id=None, action='generate'):
    
    if not category or not id:
        return {
            'status': 'failure',
            'error': 'Both category and id must be provided.'
        }
        
    print(f"Sending a <{action}> POST request to {settings.TILER_URL} for {category}-{id}.")
        
    if action == 'delete':
        data = {
            "deleteTileset": f"{category}-{id}",
        }
    else:
        # Trigger the mapdata function to generate the tileset data
        
        dummy_request = HttpRequest()
        mapdata(dummy_request, category, id, 'tileset', 'refresh')
        
        url_base = urlparse(settings.URL_FRONT).netloc
        url_base = 'dev.whgazetteer.org' if 'whgazetteer.org' not in url_base else url_base
        geoJSONUrl = f"https://{url_base}/mapdata/{category}/{id}/tileset/"
        print(f"geoJSONUrl: {geoJSONUrl}")
        data = {
            "geoJSONUrl": geoJSONUrl,
        }

    response = requests.post(settings.TILER_URL, headers={"Content-Type": "application/json"}, data=json.dumps(data))

    # Check the response status code
    print(f"TILER_URL Response status: {response.status_code}")
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("status") == "success":
            if action == 'generate':
                cache.delete(f"{category}-{id}-tileset")
            else: # action == 'delete'
                reset_standard_mapdata(category, id)
            print(f"Tileset <{action}> successful.")
            return response_data
        else:
            message = response_data.get("message")
            print(f"Tileset <{action}> failed: {message}")
    else:
        response_data = response.json()
        error = response_data.get("error")
        print(f"Tileset <{action}> failed with status {response.status_code}: {error}")

    if action == 'generate':
        reset_standard_mapdata(category, id)
    return {
        'status': 'failure',
        'error': f'Error processing tileset <{action}> request.'
    }

@login_required
@require_POST
def get_tileset_task_progress(request):
    data = json.loads(request.body)
    progress_data = []

    for item in data:
        category, id, action = item['category'], item['id'], item['action']
        task_progress = redis_client.get(f'{category}-{id}-{action}')
        progress_data.append({'category': category, 'id': id, 'action': action, 'progress': task_progress.decode('utf-8') if task_progress else None})

    return JsonResponse(progress_data, safe=False)
    