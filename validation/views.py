# validation/views.py
import json
import codecs
import logging
import uuid
import ijson
from django.conf import settings
from django.http import JsonResponse
from pyld import jsonld
from .tasks import validate_feature_batch
import redis

logger = logging.getLogger('validation')

def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

def get_memory_size(obj):
    """Estimate the memory size of an object."""
    return sys.getsizeof(obj) + sum(sys.getsizeof(v) for v in obj.values() if isinstance(obj, dict))

def process_lpf(request, file_path=settings.VALIDATION_TEST_SAMPLE):
    
    try:
        with codecs.open(settings.LPF_SCHEMA_PATH, 'r', 'utf8') as schema_file:
            schema = json.load(schema_file)
        with codecs.open(settings.LPF_CONTEXT_PATH, 'r', 'utf8') as context_file:
            context = json.load(context_file)
    except (IOError, json.JSONDecodeError) as e:
        message = f"Error reading schema or context file: {e}"
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
    
    redis_client = get_redis_client()
    task_id = f"validation_task_{uuid.uuid4()}"
    redis_client.hset(task_id, mapping={
        'status': 'in_progress',
        'start_time': timezone.now().isoformat(),
        'all_queued': False,
        'queued_features': 0,
    })

    try:
        # Process each batch of features with Celery
        for feature_batch in read_json_features_in_batches(file_path, task_id):
            compacted_batch = [jsonld.compact(feature, context) for feature in feature_batch]
            validate_feature_batch.delay(compacted_batch, schema, task_id)
            redis_client.hincrby(task_id, 'queued_features', len(compacted_batch))
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
            
        redis_client.hset(task_id, 'all_queued', True)
        redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
            
    except Exception as e:
        full_error = f"Batch processing error: {str(e)}"
        logger.error(full_error)
        redis_client.rpush(f"{task_id}_errors", full_error)
            
        redis_client.hset(task_id, mapping={
            'status': 'failed',
            'end_time': timezone.now().isoformat()
        })

        return JsonResponse({"status": "failed", "message": str(e)}, status=500)

    return JsonResponse({"status": "in_progress", "task_id": task_id})

def read_json_features_in_batches(file_path, task_id):
    """
    Streams JSON features from a file and yields batches of complete `Feature` objects
    without loading the entire file into memory.
    """
    try:
        with open(file_path, 'r') as file:
            parser = ijson.items(file, 'features.item')
            feature_batch = []
            current_memory_size = 0

            for feature in parser:
                current_memory_size += get_memory_size(feature)
                feature_batch.append(feature)

                if current_memory_size >= settings.VALIDATION_BATCH_MEMORY_LIMIT:
                    yield feature_batch
                    feature_batch = []
                    current_memory_size = 0

            # Yield any remaining features in the last batch
            if feature_batch:
                yield feature_batch

    except (IOError, ValueError) as e:
        raise

def get_task_status(task_id):
    redis_client = get_redis_client()
    status = redis_client.hgetall(task_id)
    if not status:
        return JsonResponse({"status": "not_found", "message": "Task ID not found"}, status=404)
    status = {k.decode('utf-8'): v.decode('utf-8') for k, v in status.items()}
    
    current_time = timezone.now()
    last_update_time_str = status.get('last_update', status.get('start_time'))
    last_update_time = timezone.datetime.fromisoformat(last_update_time_str)
    status['time_since_last_update'] = (current_time - last_update_time).total_seconds()
    
    status['errors'] = [error.decode('utf-8') for error in redis_client.lrange(f"{task_id}_errors", 0, -1)]
    status['task_id'] = task_id
    return JsonResponse({
        "status": "success",
        "task_status": status
    })
