import gzip
import io
import json
import logging
import os
import time

import redis
from celery import shared_task
from django.conf import settings

from api.schemas import TYPE_MAP
from api.serializers_api import PlaceFeatureSerializer

# Redis client for coordination
redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)

# File storage paths
CACHE_DIR = os.path.join(settings.MEDIA_ROOT, 'downloads')
os.makedirs(CACHE_DIR, exist_ok=True)

logger = logging.getLogger('reconciliation')


class LPFCache:
    """Manages cached LPF files and build coordination"""

    @staticmethod
    def get_cache_path(obj_type, obj_id):
        return os.path.join(CACHE_DIR, f"whg_{obj_type}_{obj_id}.lpf.gz")

    @staticmethod
    def get_build_lock_key(obj_type, obj_id):
        return f"lpf_build_lock:{obj_type}:{obj_id}"

    @staticmethod
    def get_build_task_key(obj_type, obj_id):
        return f"lpf_build_task:{obj_type}:{obj_id}"

    @staticmethod
    def get_last_rebuild_key(obj_type, obj_id):
        return f"lpf_last_rebuild:{obj_type}:{obj_id}"

    @staticmethod
    def is_cached(obj_type, obj_id):
        return os.path.exists(LPFCache.get_cache_path(obj_type, obj_id))

    @staticmethod
    def is_building(obj_type, obj_id):
        lock_key = LPFCache.get_build_lock_key(obj_type, obj_id)
        return redis_client.exists(lock_key)

    @staticmethod
    def acquire_build_lock(obj_type, obj_id, timeout=3600):
        """Acquire lock for building cache file"""
        lock_key = LPFCache.get_build_lock_key(obj_type, obj_id)
        return redis_client.set(lock_key, "building", ex=timeout, nx=True)

    @staticmethod
    def release_build_lock(obj_type, obj_id):
        lock_key = LPFCache.get_build_lock_key(obj_type, obj_id)
        redis_client.delete(lock_key)

    @staticmethod
    def store_build_task_id(obj_type, obj_id, task_id):
        """Store the Celery task ID for potential cancellation"""
        task_key = LPFCache.get_build_task_key(obj_type, obj_id)
        redis_client.set(task_key, task_id, ex=3600)  # Expire after 1 hour

    @staticmethod
    def get_build_task_id(obj_type, obj_id):
        """Get the current build task ID"""
        task_key = LPFCache.get_build_task_key(obj_type, obj_id)
        task_id = redis_client.get(task_key)
        return task_id.decode() if task_id else None

    @staticmethod
    def clear_build_task_id(obj_type, obj_id):
        """Clear the stored task ID"""
        task_key = LPFCache.get_build_task_key(obj_type, obj_id)
        redis_client.delete(task_key)

    @staticmethod
    def should_throttle_rebuild(obj_type, obj_id, throttle_seconds=300):
        """Check if rebuild should be throttled (default 5 minutes)"""
        last_rebuild_key = LPFCache.get_last_rebuild_key(obj_type, obj_id)
        last_rebuild = redis_client.get(last_rebuild_key)

        if last_rebuild:
            last_time = float(last_rebuild.decode())
            if time.time() - last_time < throttle_seconds:
                return True
        return False

    @staticmethod
    def get_pending_rebuild_key(obj_type, obj_id):
        return f"lpf_pending_rebuild:{obj_type}:{obj_id}"

    @staticmethod
    def mark_pending_rebuild(obj_type, obj_id):
        """Mark that a rebuild is needed when throttle expires"""
        pending_key = LPFCache.get_pending_rebuild_key(obj_type, obj_id)
        redis_client.set(pending_key, str(time.time()), ex=86400)  # Expire after 24 hours

    @staticmethod
    def has_pending_rebuild(obj_type, obj_id):
        """Check if there's a pending rebuild"""
        pending_key = LPFCache.get_pending_rebuild_key(obj_type, obj_id)
        return redis_client.exists(pending_key)

    @staticmethod
    def record_rebuild_time(obj_type, obj_id):
        """Record the time of rebuild trigger"""
        last_rebuild_key = LPFCache.get_last_rebuild_key(obj_type, obj_id)
        redis_client.set(last_rebuild_key, str(time.time()), ex=86400)  # Expire after 24 hours

    @staticmethod
    def delete_cache(obj_type, obj_id):
        """Delete cached file if it exists"""
        cache_path = LPFCache.get_cache_path(obj_type, obj_id)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            return True
        return False

    @staticmethod
    def cancel_current_build(obj_type, obj_id):
        """Cancel any currently running build task"""
        task_id = LPFCache.get_build_task_id(obj_type, obj_id)
        if task_id:
            try:
                # Revoke the task
                from celery import current_app
                current_app.control.revoke(task_id, terminate=True)

                # Clean up Redis keys
                LPFCache.release_build_lock(obj_type, obj_id)
                LPFCache.clear_build_task_id(obj_type, obj_id)

                return True
            except Exception as e:
                # Log the error but continue
                print(f"Error canceling build task {task_id}: {e}")
        return False


def lpf_stream_from_file(filepath):
    """Stream a pre-built gzipped cache file"""
    logger.debug(f"Starting to stream from cached file: {filepath}")
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            yield chunk


def lpf_stream_live(obj_type, obj, request, cache_filepath=None):
    """
    Stream LPF live while writing to gzipped cache file.
    """
    cache_file = None
    if cache_filepath:
        cache_file = open(cache_filepath + '.tmp', 'wb')

    # Buffer for compressing incrementally
    buffer = io.BytesIO()
    gzip_file = gzip.GzipFile(fileobj=buffer, mode='w')

    def write_and_yield(data: str):
        gzip_file.write(data.encode('utf-8'))  # write into gzip stream
        gzip_file.flush()
        buffer.seek(0)
        chunk = buffer.read()
        if chunk:
            if cache_file:
                cache_file.write(chunk)
            yield chunk
        buffer.truncate(0)
        buffer.seek(0)

    try:
        yield from write_and_yield(
            '{"@context":"https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld","type":"FeatureCollection"'
        )

        citation = getattr(obj, "citation_csl", None)
        if citation:
            yield from write_and_yield(',"citation":' + json.dumps(citation))

        licence_text = (
            "Unless specified otherwise, all content created for or uploaded to the World Historical Gazetteer — "
            "including editorial content, documentation, images, and contributed datasets and collections — "
            "is licensed under a Creative Commons Attribution-NonCommercial 4.0 International License. "
            "Externally hosted datasets and content that are linked to by WHG remain under the copyrights "
            "and licenses specified by their original contributors."
        )
        yield from write_and_yield(',"license":' + json.dumps(licence_text))
        yield from write_and_yield(',"features":[')

        first = True
        if obj_type == "dataset":
            qs = obj.places.all()
        elif obj_type == "collection" and obj.collection_class == "dataset":
            yield from write_and_yield(
                '],"error":{"message":"Dataset collections may not be downloaded. Please download each constituent dataset individually."}}'
            )
            return
        elif obj_type == "collection" and obj.collection_class == "place":
            qs = obj.places.all()
        else:
            yield from write_and_yield(
                '],"error":{"message":"LPF export by streaming is only supported for datasets and place collections."}}'
            )
            return

        for place in qs.iterator():
            if not first:
                yield from write_and_yield(',')
            else:
                first = False

            feature = PlaceFeatureSerializer(place, context={"request": request}).data
            yield from write_and_yield(json.dumps(feature))

        yield from write_and_yield(']')
        yield from write_and_yield('}')

        # Finish gzip stream properly
        gzip_file.close()
        buffer.seek(0)
        trailer = buffer.read()
        if trailer:
            if cache_file:
                cache_file.write(trailer)
            yield trailer

    finally:
        if cache_file:
            cache_file.close()
            if os.path.exists(cache_filepath + '.tmp'):
                os.rename(cache_filepath + '.tmp', cache_filepath)


@shared_task(bind=True)
def build_lpf_cache(self, obj_type, obj_id):
    """Celery task to build LPF cache file in background"""
    try:
        logger.info(f"Starting cache build for {obj_type}:{obj_id}")
        # Store task ID for potential cancellation
        LPFCache.store_build_task_id(obj_type, obj_id, self.request.id)

        config = TYPE_MAP.get(obj_type)
        if not config:
            return f"Unsupported object type: {obj_type}"

        # Get the object
        model_class = config["model"]
        obj = model_class.objects.get(pk=obj_id)

        cache_path = LPFCache.get_cache_path(obj_type, obj_id)

        # Build the cache file (gzipped)
        with gzip.open(cache_path + '.tmp', 'wt', encoding='utf-8') as cache_file:
            # Use the live streaming function but only write to file
            for chunk in lpf_stream_live(obj_type, obj, None, None):
                cache_file.write(chunk)

                # Check if task has been revoked
                if self.is_aborted():
                    cache_file.close()
                    # Clean up temp file
                    if os.path.exists(cache_path + '.tmp'):
                        os.remove(cache_path + '.tmp')
                    return f"Build task for {obj_type}:{obj_id} was cancelled"

        # Atomically move to final location
        os.rename(cache_path + '.tmp', cache_path)
        logger.info(f"Finished cache build for {obj_type}:{obj_id}")

        return f"Successfully built LPF cache for {obj_type}:{obj_id}"

    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(cache_path + '.tmp'):
            os.remove(cache_path + '.tmp')
        return f"Failed to build LPF cache for {obj_type}:{obj_id}: {str(e)}"

    finally:
        LPFCache.release_build_lock(obj_type, obj_id)
        LPFCache.clear_build_task_id(obj_type, obj_id)


# Signal-triggered cache management
def invalidate_and_rebuild_lpf_cache(obj_type, obj_id, force=False):
    """
    Signal-triggered function to invalidate and rebuild LPF cache.

    Args:
        obj_type: Type of object ('dataset', 'collection')
        obj_id: Object ID
        force: Skip throttling if True

    Returns:
        dict: Status information about the operation
    """
    result = {
        'cancelled_existing': False,
        'deleted_cache': False,
        'started_rebuild': False,
        'throttled': False,
        'deferred': False,
        'message': ''
    }

    # Check throttling unless forced
    if not force and LPFCache.should_throttle_rebuild(obj_type, obj_id):
        # Instead of blocking, schedule a deferred rebuild
        LPFCache.mark_pending_rebuild(obj_type, obj_id)

        # Schedule the deferred rebuild task
        time_since_last = time.time() - float(
            redis_client.get(LPFCache.get_last_rebuild_key(obj_type, obj_id)).decode())
        delay_seconds = max(300 - time_since_last + 10, 10)  # At least 10 seconds from now

        deferred_lpf_rebuild.apply_async(
            args=[obj_type, obj_id],
            countdown=int(delay_seconds)
        )

        result['throttled'] = True
        result['deferred'] = True
        result['message'] = f"Rebuild deferred for {obj_type}:{obj_id} (will rebuild in {int(delay_seconds)} seconds)"
        return result

    # Cancel any current build
    if LPFCache.cancel_current_build(obj_type, obj_id):
        result['cancelled_existing'] = True

    # Delete existing cache
    if LPFCache.delete_cache(obj_type, obj_id):
        result['deleted_cache'] = True

    # Clear any pending rebuild since we're doing it now
    LPFCache.clear_pending_rebuild(obj_type, obj_id)

    # Record rebuild time for throttling
    LPFCache.record_rebuild_time(obj_type, obj_id)

    # Start new build if we can acquire the lock
    if LPFCache.acquire_build_lock(obj_type, obj_id):
        task = build_lpf_cache.delay(obj_type, obj_id)
        result['started_rebuild'] = True
        result['message'] = f"Started rebuild for {obj_type}:{obj_id} (task: {task.id})"
    else:
        result['message'] = f"Could not acquire lock for {obj_type}:{obj_id}"

    return result


@shared_task
def deferred_lpf_rebuild(obj_type, obj_id):
    """
    Celery task for deferred rebuilds - only rebuilds if still pending
    """
    # Only rebuild if there's still a pending rebuild
    if LPFCache.has_pending_rebuild(obj_type, obj_id):
        # Check if we're still within throttle period
        if not LPFCache.should_throttle_rebuild(obj_type, obj_id):
            result = invalidate_and_rebuild_lpf_cache(obj_type, obj_id, force=True)
            return f"Deferred rebuild completed for {obj_type}:{obj_id}: {result['message']}"
        else:
            # Still throttled, reschedule for later
            deferred_lpf_rebuild.apply_async(
                args=[obj_type, obj_id],
                countdown=60  # Try again in 1 minute
            )
            return f"Deferred rebuild rescheduled for {obj_type}:{obj_id}"
    else:
        return f"No pending rebuild for {obj_type}:{obj_id} - skipping"


# Optional: Management command or API endpoint to pre-build caches
def prebuild_lpf_cache(obj_type, obj_id, force_rebuild=False):
    """
    Helper function to trigger LPF cache building.

    Args:
        obj_type: Type of object ('dataset', 'collection')
        obj_id: Object ID
        force_rebuild: If True, rebuild even if cache exists

    Returns:
        bool: True if build was triggered, False otherwise
    """
    if force_rebuild:
        return invalidate_and_rebuild_lpf_cache(obj_type, obj_id, force=True)['started_rebuild']

    if not LPFCache.is_cached(obj_type, obj_id) and not LPFCache.is_building(obj_type, obj_id):
        if LPFCache.acquire_build_lock(obj_type, obj_id):
            build_lpf_cache.delay(obj_type, obj_id)
            return True
    return False


# Example signal handlers for Dataset and place Collections only
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

@receiver(post_save, sender=Dataset)
def dataset_saved(sender, instance, **kwargs):
    # Only rebuild on Dataset save, not individual Place changes
    invalidate_and_rebuild_lpf_cache('dataset', instance.id)

@receiver(post_delete, sender=Dataset)
def dataset_deleted(sender, instance, **kwargs):
    LPFCache.delete_cache('dataset', instance.id)
    LPFCache.cancel_current_build('dataset', instance.id)

@receiver(post_save, sender=Collection)
def collection_saved(sender, instance, **kwargs):
    # Only rebuild place collections, not dataset collections
    if instance.collection_class == 'place':
        invalidate_and_rebuild_lpf_cache('collection', instance.id)

@receiver(post_delete, sender=Collection)
def collection_deleted(sender, instance, **kwargs):
    if instance.collection_class == 'place':
        LPFCache.delete_cache('collection', instance.id)
        LPFCache.cancel_current_build('collection', instance.id)

@receiver(m2m_changed, sender=Collection.places.through)
def collection_places_changed(sender, instance, action, pk_set, **kwargs):
    # Only for place collections when places are added/removed
    if action in ['post_add', 'post_remove', 'post_clear'] and instance.collection_class == 'place':
        invalidate_and_rebuild_lpf_cache('collection', instance.id)
"""
