import json
import logging
import os
import time
from itertools import chain, islice

import networkx as nx
import numpy as np
import redis
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import GeometryCollection, Polygon
from django.core.cache import cache
from django.core.cache.backends.filebased import FileBasedCache
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone

from collection.models import Collection
from collection.views import year_from_string
from datasets.models import Dataset
from places.models import Place, PlaceGeom, CloseMatch

logger = logging.getLogger('mapdata')


def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)


def compute_minmax(places_info):
    """
    Computes the global min and max values from a list of place info dicts.
    Expects each dict to have string 'min' and 'max' keys.
    Returns a [min, max] list as strings, or [None, None] if unavailable.
    """
    try:
        arr = np.array([
            (float(p["min"]), float(p["max"]))
            for p in places_info
            if p["min"] != "null" and p["max"] != "null"
        ])
        if arr.size > 0:
            return [str(np.min(arr[:, 0])), str(np.max(arr[:, 1]))]
    except Exception as e:
        logger.warning(f"Failed to compute minmax: {e}")
    return [None, None]


@shared_task
def mapdata_task(category, id, refresh=False):
    dummy_request = HttpRequest()
    dummy_request.user = AnonymousUser()

    result = mapdata(dummy_request, category, id, refresh=refresh)
    if isinstance(result, JsonResponse):
        return result.json()
    else:
        raise ValueError("`mapdata` function did not return a JsonResponse")


def reset_mapdata(category, id):
    logger.debug(f"Resetting mapdata for {category}-{id}.")
    mapdata_task.delay(category, id, refresh=True)


def mapdata(request, category, id, refresh='false'):
    # TODO: Fix use of <category>/<id>/refresh/full to bypass geometry reduction in PLACE branch
    refresh = str(refresh).lower() in ['refresh', 'true', '1', 'yes']
    cache_key = f"{category}-{id}"
    logger.debug(f"Mapdata requested for {cache_key} (refresh={refresh}).")

    # Check if cached data exists and return it if found
    if not refresh:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Found cached mapdata.")
            return JsonResponse(cached_data, safe=False, json_dumps_params={'ensure_ascii': False})

    cache.delete(cache_key)
    start_time = time.time()

    mapdata_result = mapdata_dataset(id) if category == "datasets" else mapdata_collection(id)

    response_time = time.time() - start_time
    logger.debug(f"Mapdata generation time: {response_time:.2f} seconds")

    if response_time > 1:
        logger.debug("Caching mapdata.")
        cache.set(cache_key, mapdata_result)
    else:
        logger.debug("No need to cache mapdata.")

    return JsonResponse(mapdata_result, safe=False, json_dumps_params={'ensure_ascii': False})


def buffer_extent(extent, buffer_distance=0.1):
    return Polygon.from_bbox(extent).buffer(buffer_distance).extent if extent else None


def buffered_extent_from_bbox(bbox, buffer_distance=0.1):
    return bbox.buffer(buffer_distance).extent if isinstance(bbox, Polygon) else None


def mapdata_dataset(id, task_id=None, chunk_size=1000):
    ds = get_object_or_404(Dataset, pk=id)

    if task_id:
        redis_client = get_redis_client()
        redis_client.hset(task_id, 'mapdata_start_time', timezone.now().isoformat())
        redis_client.hset(task_id, 'queued_features', ds.numrows)

    features = []
    redis_batch_size = 100
    index = 0

    # Get the extent directly from the dataset's bbox
    buffered_extent = buffered_extent_from_bbox(ds.bbox)

    # Prefetch related geometries using Prefetch object
    places_qs = ds.places.prefetch_related(
        Prefetch(
            'geoms',
            queryset=PlaceGeom.objects.only('place_id', 'jsonb', 'geom'),
            to_attr='prefetched_geoms'
        )
    ).values('id', 'title', 'fclasses', 'review_wd', 'review_tgn', 'review_whg', 'minmax').order_by('id')

    place_iterator = iter(places_qs)

    while True:
        chunk = list(islice(place_iterator, chunk_size))
        if not chunk:
            break

        place_ids = [place['id'] for place in chunk]

        # Fetch full Place instances with prefetched geoms
        full_places = ds.places.filter(id__in=place_ids).prefetch_related(
            Prefetch(
                'geoms',
                queryset=PlaceGeom.objects.only('place_id', 'jsonb', 'geom'),
                to_attr='prefetched_geoms'
            )
        )

        place_map = {p.id: p for p in full_places}

        for place in chunk:
            place_obj = place_map[place['id']]
            geom_list = [g.jsonb for g in getattr(place_obj, 'prefetched_geoms', [])]

            feature = {
                "type": "Feature",
                "properties": {
                    "pid": place['id'],
                    "title": place['title'],
                    "fclasses": place['fclasses'],
                    "review_wd": place['review_wd'],
                    "review_tgn": place['review_tgn'],
                    "review_whg": place['review_whg'],
                    "min": "null" if place['minmax'] is None or place['minmax'][0] is None else place['minmax'][0],
                    "max": "null" if place['minmax'] is None or place['minmax'][1] is None else place['minmax'][1],
                },
                "geometry": geom_list[0] if len(geom_list) == 1
                else (
                    None if len(geom_list) == 0
                    else {
                        "type": "GeometryCollection",
                        "geometries": geom_list
                    }
                ),
                "id": index
            }
            features.append(feature)

            if task_id and (index + 1) % redis_batch_size == 0:
                redis_client.hincrby(task_id, 'queued_features', -redis_batch_size)

            index += 1

    if task_id:
        redis_client.hincrby(task_id, 'queued_features', -(index % redis_batch_size))

    return {
        "title": ds.title,
        "contributors": ds.contributors,
        "citation": ds.citation,
        "creator": ds.creator,
        "minmax": ds.minmax,
        "extent": buffered_extent,
        "type": "FeatureCollection",
        "features": features,
    }


def mapdata_collection(id):
    collection = get_object_or_404(Collection, id=id)

    feature_collection = {
        "title": collection.title,
        "creator": collection.creator,
        "type": "FeatureCollection",
        "features": [],
        "extent": buffered_extent_from_bbox(collection.bbox)
    }

    if collection.collection_class == 'place':
        return mapdata_collection_place(collection, feature_collection)
    else:
        return mapdata_collection_dataset(collection, feature_collection)


def mapdata_collection_place(collection, feature_collection):
    traces = collection.traces.filter(archived=False).select_related('place')
    reduce_geometry = any(facet.get("trail") for facet in collection.vis_parameters.values())
    feature_collection["relations"] = collection.rel_keywords

    # Prefetch geoms for places to avoid querying them multiple times
    places = {trace.place.id: trace.place for trace in traces.prefetch_related('place__geoms')}

    for index, trace in enumerate(traces):
        place = places[trace.place.id]
        first_anno_sequence = place.annos.first().sequence if place.annos.exists() else None
        reference_place = place.matches[0] if trace.include_matches and place.matches else place

        geometry_collection = None
        if reference_place.geoms.exists():
            # Perform the union of geometries only once for the place
            unioned_geometry = reference_place.geoms.aggregate(union=Union('geom'))['union']
            if unioned_geometry:
                try:
                    centroid = unioned_geometry.centroid if reduce_geometry else None
                    geometry_collection = json.loads(
                        GeometryCollection(centroid if centroid else unioned_geometry).geojson)
                except (TypeError, ValueError) as e:
                    logger.debug(f"Error with geometry collection for place {place.id}: {e}", unioned_geometry)
                    geometry_collection = json.loads(
                        GeometryCollection(centroid if centroid else list(unioned_geometry)).geojson)

        feature = {
            "type": "Feature",
            "properties": {
                "pid": place.id,
                "cid": collection.id,
                "title": place.title,
                "fclasses": place.fclasses,
                "ccodes": place.ccodes,
                "relation": trace.relation[0] if trace.relation else None,
                "min": year_from_string(trace.start) if trace.start else None,
                "max": year_from_string(trace.end) if trace.end else None,
                "note": trace.note,
                "seq": first_anno_sequence,
            },
            "geometry": geometry_collection,
            "id": index,
        }

        if trace.include_matches and place != reference_place:
            feature["properties"]["geometry_pid"] = reference_place.id

        feature_collection["features"].append(feature)

    return feature_collection


def mapdata_collection_dataset(collection, feature_collection):
    '''
    Construct families of matched places within collection
    '''

    # Prefetch geoms for all places in collection
    collection_places_all = collection.places_all.prefetch_related('geoms')

    # Get close matches in one query
    close_matches = CloseMatch.objects.filter(
        Q(place_a__in=collection_places_all) & Q(place_b__in=collection_places_all)
    ).values_list('place_a_id', 'place_b_id')

    # Create a graph of close matches (using networkx)
    G = nx.Graph(close_matches) if close_matches else nx.Graph()
    families = list(nx.connected_components(G))

    # Process unmatched places
    unmatched_places = collection_places_all.exclude(id__in=G.nodes).order_by('id')

    logger.debug(
        f"Collection {collection.id}: {collection_places_all.count()} places sorted into {len(families)} families and {len(unmatched_places)} unmatched.")

    # Helper function to aggregate place information
    def aggregate_place_info(place):
        geometries = place.geoms.all() or None
        geometry_collection = None
        if geometries:
            unioned_geometry = geometries.aggregate(union=Union('geom'))['union']
            if unioned_geometry:
                try:
                    geometry_collection = json.loads(GeometryCollection(unioned_geometry).geojson)
                except (TypeError, ValueError) as e:
                    logger.debug(f"Error with geometry collection for place {place.id}: {e}", unioned_geometry)
                    geometry_collection = json.loads(GeometryCollection(list(unioned_geometry)).geojson)

        place_min, place_max = place.minmax or (None, None)
        return {
            "id": str(place.id),
            "src_id": [place.src_id] if isinstance(place.src_id, int) else place.src_id,
            "title": place.title,
            "fclasses": sorted(set(fc for fc in place.fclasses if fc)) if place.fclasses else [],
            "ccodes": place.ccodes,
            "min": "null" if place_min is None else place_min,
            "max": "null" if place_max is None else place_max,
            "seq": None,
            "geometry": geometry_collection
        }

    # Aggregate info for unmatched places
    places_info = [aggregate_place_info(place) for place in unmatched_places]

    # Process families of places
    for family in families:
        family_members = Place.objects.filter(id__in=family)
        family_place_geoms = PlaceGeom.objects.filter(place_id__in=family)

        # Create a pseudo "family" place object for aggregation
        family_place = type('FamilyPlace', (object,), {})()
        family_place.id = "-".join(str(place_id) for place_id in sorted(family))

        # Directly use set and sorted to handle duplicates efficiently
        family_place.src_id = sorted(set(family_members.values_list('src_id', flat=True)))
        family_place.title = "|".join(set(family_members.values_list('title', flat=True)))
        family_place.ccodes = sorted(set(chain.from_iterable(family_members.values_list('ccodes', flat=True))))
        family_place.fclasses = sorted(
            set(chain.from_iterable(filter(None, family_members.values_list('fclasses', flat=True)))))

        family_place.minmax = compute_minmax([
            {"min": str(m[0]), "max": str(m[1])}
            for m in family_members.values_list('minmax')
            if m[0] is not None and m[1] is not None
        ])

        family_place.geoms = family_place_geoms
        family_place.seq = None

        family_info = aggregate_place_info(family_place)
        places_info.append(family_info)

    # Sort places and add to feature collection
    places_info.sort(key=lambda x: x['id'])
    places_info = [{'pid': place_info.pop('id'), **place_info} for place_info in places_info]

    dataset_lookup = {
        str(place.id): set(ds.id for ds in collection.datasets.filter(places=place))
        for place in collection_places_all
    }

    for index, place_info in enumerate(places_info):
        pid_values = place_info['pid'].split('-') if isinstance(place_info['pid'], str) else [place_info['pid']]
        unique_ids = {
            dataset_id
            for pid in pid_values
            if pid.isdigit() and pid in dataset_lookup  # Check if pid is a digit and exists in dataset_lookup
            for dataset_id in dataset_lookup[pid]  # Get the datasets corresponding to the place_id (pid)
        }
        place_info["relation"] = "-".join(sorted(str(unique_id) for unique_id in unique_ids))

        # Construct the feature object for the collection
        feature = {
            "type": "Feature",
            "geometry": place_info.pop('geometry'),
            "properties": place_info,
            "id": index
        }
        feature_collection["features"].append(feature)

    # Aggregate min-max values for the feature collection
    min_max_values = [(float(place_info["min"]), float(place_info["max"])) for place_info in places_info if
                      place_info["min"] != "null" and place_info["max"] != "null"]
    feature_collection["minmax"] = compute_minmax([
        {"min": str(v[0]), "max": str(v[1])}
        for v in min_max_values
        if v[0] is not None and v[1] is not None
    ])

    return feature_collection


class MapdataFileBasedCache(FileBasedCache):
    def __init__(self, dir, params):
        super().__init__(dir, params)

    def _cull(self):
        """
        Custom cull implementation: Remove the smallest cache entries if max_entries is reached.
        """
        filelist = self._list_cache_files()
        num_entries = len(filelist)
        if num_entries < self._max_entries:
            return  # return early if no culling is required
        if self._cull_frequency == 0:
            return self.clear()  # Clear the cache when CULL_FREQUENCY = 0

        # Sort filelist by file size
        filelist.sort(key=lambda x: os.path.getsize(x))

        # Delete the oldest entries
        num_to_delete = int(num_entries / self._cull_frequency)
        for fname in filelist[:num_to_delete]:
            self._delete(fname)
