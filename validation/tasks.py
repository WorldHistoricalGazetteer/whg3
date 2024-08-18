# validation/tasks.py
import json
import logging
from celery import shared_task
from jsonschema import Draft202012Validator, ValidationError
from django.utils import timezone
from .views import get_redis_client, get_task_status

logger = logging.getLogger('validation')

@shared_task
def validate_feature_batch(compacted_batch, schema, task_id):
    validator = Draft202012Validator(schema)
    redis_client = get_redis_client()

    for feature in compacted_batch:
        try:
            validator.validate(feature)
        except ValidationError as e:
            error_message = e.message
            error_path = " -> ".join([str(p) for p in e.absolute_path])
            detailed_error = parse_validation_error(e)
            full_error = f"Validation error at {error_path}: {detailed_error}"
            logger.error(full_error)
            redis_client.rpush(f"{task_id}_errors", full_error)
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())

        redis_client.hincrby(task_id, 'queued_features', -1)
        redis_client.hset(task_id, 'last_update', timezone.now().isoformat())

    # Check if all tasks are done
    task_status = redis_client.hgetall(task_id)
    all_queued = task_status.get(b'all_queued')
    queued_features = int(task_status.get(b'queued_features', 0))
    
    if all_queued and queued_features == 0:
        redis_client.hset(task_id, mapping={
            'status': 'complete',
            'end_time': timezone.now().isoformat()
        })

def parse_validation_error(error):
    # Currently, this returns a simple string representation of the error.
    # Future implementation might add more detailed parsing here.
    return str(error)
