# validation/tasks.py
import json
import logging
from celery import shared_task
from jsonschema import Draft202012Validator, ValidationError

logger = logging.getLogger('validation')

@shared_task
def validate_chunk(chunk, schema):
    validator = Draft202012Validator(schema)
    errors = []

    for data in chunk:
        try:
            validator.validate(data)
        except ValidationError as e:
            errors.append(e.message)
            error_path = " -> ".join([str(p) for p in e.absolute_path])
            detailed_error = parse_validation_error(e)
            logger.error(f"Validation error at {error_path}: {detailed_error}")

    return errors
