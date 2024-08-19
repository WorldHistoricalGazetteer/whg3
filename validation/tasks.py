# validation/tasks.py
import json
import logging
from celery import shared_task
from jsonschema import Draft7Validator, ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
import redis

logger = logging.getLogger('validation')

def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

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

@shared_task
def validate_feature_batch(feature_batch, schema, task_id):
    
    validator = Draft7Validator(schema)
    
    redis_client = get_redis_client()

    for feature in feature_batch:
        wrapped_feature = {
            "type": "FeatureCollection",
            "features": [feature]
        }
        try:
            logger.debug(f'Validating feature: {feature}')
            validator.validate(wrapped_feature)
            logger.debug(f'Validated feature: {feature}')
        except ValidationError as e:
            error_message = e.message
            error_path = " -> ".join([str(p) for p in e.absolute_path])
            detailed_error = parse_validation_error(e)
            full_error = f"Validation error at {error_path}: {detailed_error}"
            logger.error(full_error)
            redis_client.rpush(f"{task_id}_errors", full_error)
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            redis_client.rpush(f"{task_id}_errors", str(e))
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())

        try:
            redis_client.hincrby(task_id, 'queued_features', -1)
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
        except Exception as e:
            logger.error(f"Error updating Redis status: {e}")

    # Check if all tasks are done
    try:
        task_status = redis_client.hgetall(task_id)
        all_queued = task_status.get(b'all_queued', b'').decode('utf-8')
        total_features = int(task_status.get(b'total_features', 0))
        queued_features = int(task_status.get(b'queued_features', 0))
        
        start_time_str = task_status.get(b'start_time', b'').decode('utf-8')
        if start_time_str:
            start_time = timezone.datetime.fromisoformat(start_time_str)
        else:
            start_time = timezone.now()
        
        end_time = timezone.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        if all_queued == 'true' and queued_features == 0:
            redis_client.hset(task_id, mapping={
                'status': 'complete',
                'end_time': end_time.isoformat(),
                'time_taken': elapsed_time,
                'time_remaining': 0
            })
            logger.debug(f'Task {task_id} completed successfully.')
        else:
            if total_features > queued_features:
                estimated_total_time = (elapsed_time / (total_features - queued_features)) * total_features
                estimated_time_remaining = estimated_total_time - elapsed_time
            else:
                estimated_time_remaining = 0            
            redis_client.hset(task_id, 'time_remaining', estimated_time_remaining)
            logger.debug(f'Task {task_id} not yet complete. Status: {task_status}')
    except Exception as e:
        logger.error(f"Error checking or updating task status: {e}")

def parse_validation_error(error: ValidationError) -> str:
    # Get the part of the schema that failed validation
    schema_path = " -> ".join([str(p) for p in error.schema_path])
    
    # Get the path within the instance (the JSON being validated)
    instance_path = " -> ".join([str(p) for p in error.absolute_path])
    
    # Get the error message and value that caused the error
    error_message = error.message
    error_value = error.instance
    
    # Format the message for better readability
    formatted_error = (
        f"Error Type: {error.validator} ({error.validator_value})\n"
        f"Schema Path: {schema_path}\n"
        f"Instance Path: {instance_path}\n"
        f"Invalid Value: {error_value}\n"
        f"Message: {error_message}"
    )
    
    return formatted_error
