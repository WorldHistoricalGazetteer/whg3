from celery import shared_task
from vespa.utils import feed_file_to_vespa

@shared_task
def async_feed_file_to_vespa(file_path, endpoint_url):
    return feed_file_to_vespa(file_path, endpoint_url)
