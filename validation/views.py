# validation/views.py
import json
import codecs
import logging
import uuid
import ijson
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from pyld import jsonld
from .tasks import validate_feature_batch
import redis
import sys

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
        'all_queued': 'false',
        'total_features': 0,
        'queued_features': 0,
    })

    try:
        # Process each batch of features with Celery
        for feature_batch in read_json_features_in_batches(file_path, task_id):
            # The following line could be implemented if the LP Ontology were correct
            #feature_batch = [jsonld.compact(feature, context) for feature in feature_batch]
            validate_feature_batch.delay(feature_batch, schema, task_id)
            feature_count = len(feature_batch)
            redis_client.hincrby(task_id, 'total_features', feature_count)
            redis_client.hincrby(task_id, 'queued_features', feature_count)
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
            
        redis_client.hset(task_id, 'all_queued', 'true')
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
            logger.debug(f'Opened {file_path}...')
            parser = ijson.items(file, 'features.item', use_float=True)
            feature_batch = []
            current_memory_size = 0

            logger.debug(f'Parsing batch from {file_path} with parser: {type(parser)}')
            for feature in parser:
                current_memory_size += get_memory_size(feature)
                feature_batch.append(feature)

                if current_memory_size >= settings.VALIDATION_BATCH_MEMORY_LIMIT:
                    logger.debug(f'Yielding final batch ({current_memory_size} bytes): {feature_batch}')
                    yield feature_batch
                    feature_batch = []
                    current_memory_size = 0

            # Yield any remaining features in the last batch
            if feature_batch:
                logger.debug(f'Yielding final batch ({current_memory_size} bytes): {feature_batch}')
                yield feature_batch

    except (IOError, ValueError) as e:
        logger.error(f"Error reading JSON features in batches: {e}")
        raise
