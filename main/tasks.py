import redis
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)  # Use the service name from Docker Compose for the host

from celery import shared_task
# from celery_progress.backend import ProgressRecorder
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
import json
import requests
import subprocess


@shared_task()
def calculate_geometry_complexity(dataset_id):
    from datasets.models import Dataset

    dataset = Dataset.objects.get(id=dataset_id)
    complexity = dataset.coordinates_count

    return complexity


@shared_task
def check_services():
    """
    Check the status of various services and ping Healthchecks.io accordingly.
    """
    services = getattr(settings, 'HEALTHCHECKS', {})

    for service, details in services.items():
        try:
            if service == 'elasticsearch':
                # Special case for Elasticsearch until it is moved to a Docker container
                status = check_elasticsearch()
            elif service == 'tileboss':
                # Special case for Tileboss until it is moved to a Docker container
                status = check_elasticsearch()
            else:
                # General case for Docker containers
                status = get_container_health(service)

            healthcheck_url = details.get('healthcheck_url', '')
            if status != 'healthy':
                healthcheck_url += '/fail'

            logger.info(f"Service '{service}' status: {status}")
            logger.info(f"Pinging healthcheck URL: {healthcheck_url}")

            try:
                response = requests.get(f"{healthcheck_url}")
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to ping Healthchecks.io for {service}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error checking service '{service}': {e}", exc_info=True)


def get_container_health(container_id):
    """
    Get the health status of a service based on its Docker container health.
    """

    command = f"docker --tlsverify --tlscacert=/certs/ca.pem --tlscert=/certs/client-cert.pem --tlskey=/certs/client-key.pem -H={settings.DOCKER_HOST_IP} inspect --format='{{{{json .State.Health}}}}' {container_id}_{settings.ENV_CONTEXT}_{settings.BRANCH}"
    # logger.debug(command)

    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            try:
                health_json = result.stdout
                container_info = json.loads(health_json)
                health_status = container_info.get('Status', 'unknown')
                return 'healthy' if health_status == 'healthy' else 'unhealthy'
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for container health check: {e}")
                return 'unhealthy'
        else:
            logger.error(f"Container health check command failed with return code {result.returncode}")
            return 'unhealthy'
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing container health check command: {e}")
        return 'unhealthy'


# TODO: Remove this once ElasticSearch has been moved to a Docker container
def check_elasticsearch():
    """
    Check Elasticsearch health
    """
    command = f'curl -u elastic:{settings.ELASTIC_PASSWORD} -k -X GET "{settings.ES_SCHEME}://{settings.ES_HOST}:{settings.ES_PORT}/_cluster/health"'
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            try:
                output = result.stdout.decode()
                response_json = json.loads(output)
                status = response_json.get('status', '')
                if status in ['green', 'yellow']:
                    return 'healthy'
                else:
                    return 'unhealthy'
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for Elasticsearch health check: {e}")
                return 'unhealthy'
        else:
            logger.error(f"Elasticsearch health check command failed with return code {result.returncode}")
            return 'unhealthy'
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing Elasticsearch health check command: {e}")
        return 'unhealthy'


# TODO: Remove this once Tileserver has been moved to a Docker container
def check_tileboss():
    """
    Check Tileserver health by verifying the JSON response.
    """
    command = f'curl {settings.TILEBOSS}/index.json'
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            try:
                output = result.stdout.decode()
                response_json = json.loads(output)
                if isinstance(response_json, list) and len(response_json) > 0:
                    first_tileset = response_json[0]
                    if "tiles" in first_tileset and "name" in first_tileset:
                        return 'healthy'
                    else:
                        logger.error("Unexpected JSON structure in Tileserver response")
                        return 'unhealthy'
                else:
                    logger.error("Tileserver returned an empty or invalid JSON list")
                    return 'unhealthy'
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for Tileserver health check: {e}")
                return 'unhealthy'
        else:
            logger.error(f"Tileserver health check command failed with return code {result.returncode}")
            return 'unhealthy'
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing Tileserver health check command: {e}")
        return 'unhealthy'

# @shared_task
# def backup_data():
#
#     es = settings.ES_CONN
#     snapshot_name = f'Elastic_{datetime.now().strftime("%Y%m%d%H%M%S")}'
#     es.snapshot.create(repository='GCS-WHG-Backups', snapshot=snapshot_name, wait_for_completion=True)
