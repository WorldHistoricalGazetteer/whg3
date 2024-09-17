from celery import shared_task
from django.conf import settings
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import GeometryCollection, Polygon
from django.core.cache import cache
from django.core.cache.backends.filebased import FileBasedCache
from django.db.models import Min, Max, Prefetch, F, Q
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone

from collection.models import Collection
from collection.views import year_from_string
from datasets.models import Dataset
from itertools import chain, islice
from places.models import Place, PlaceGeom, Type, CloseMatch

import networkx as nx
import os, requests, time, json
import redis


def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)


@shared_task
def mapdata_task(category, id, variant=None, refresh=False):
    dummy_request = HttpRequest()
    response = mapdata(dummy_request, category, id, variant=variant, refresh=str(refresh))

    return json.loads(response.content) if isinstance(response, JsonResponse) else {'status': 'failure',
                                                                                    'error': 'Failed to generate mapdata'}


def reset_standard_mapdata(category, id):
    # This will generate standard mapdata and also delete any existing standard or tileset mapdata cache
    print(f"Resetting standard mapdata for {category}-{id}.")
    mapdata_task.delay(category, id, 'standard', 'refresh')


def mapdata(request, category, id, variant='standard', refresh='false'):  # variant options are "standard" | "tileset"
    refresh = variant == 'refresh' or refresh.lower() in ['refresh', 'true', '1', 'yes']
    if variant != 'tileset':
        variant = 'standard'
    # Generate cache key
    cache_key = f"{category}-{id}-{variant}"
    print(f"Mapdata requested for {cache_key} (refresh={refresh}).")

    # Check if cached data exists and return it if found
    if refresh == False:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print("Found cached mapdata.")
            return JsonResponse(cached_data, safe=False, json_dumps_params={'ensure_ascii': False})

    # Ensure that cache will be refreshed
    cache.delete(f"{category}-{id}-standard")

    start_time = time.time()  # Record the start time

    # If variant is not 'tileset', fetch available tilesets
    available_tilesets = []
    if variant == "standard":
        # Clean up any existing tileset cache
        cache.delete(f"{category}-{id}-tileset")
        tiler_url = os.environ.get('TILER_URL')  # Must be set in /.env/.dev-whg3
        response = requests.post(tiler_url, json={"getTilesets": {"type": category, "id": id}})

        if response.status_code == 200:
            available_tilesets = response.json().get('tilesets', [])
            print("available_tilesets", available_tilesets)

    # Determine feature collection generation based on category
    mapdata_result = mapdata_dataset(id) if category == "datasets" else mapdata_collection(id)

    end_time = time.time()  # Record the end time
    response_time = end_time - start_time  # Calculate the response time
    print(f"Mapdata generation time: {response_time:.2f} seconds")

    def reduced_geometry(mapdata_result):
        mapdata_result["features"] = [
            {**feature, "geometry": {"type": feature["geometry"]["type"]} if feature.get("geometry") else None}
            for feature in mapdata_result["features"]
        ]
        mapdata_result["tilesets"] = available_tilesets
        return mapdata_result

    if variant == "tileset":
        print(f"Splitting and caching mapdata.")

        # Reduce feature properties in mapdata to be fetched by tiler
        mapdata_tileset = mapdata_result.copy()
        mapdata_tileset["features"] = [
            {**feature, "properties": {k: v for k, v in feature["properties"].items() if
                                       k in ["fclasses", "relation", "pid", "min", "max"]}}
            for feature in mapdata_tileset["features"]
        ]
        cache.set(f"{category}-{id}-tileset", mapdata_tileset)

        # Reduce feature geometry in mapdata sent to browser
        new_tileset = f"{category}-{id}"
        if new_tileset not in available_tilesets:
            available_tilesets.append(new_tileset)
        cache.set(f"{category}-{id}-standard", reduced_geometry(mapdata_result))

    elif response_time > 1:  # Cache if generation time exceeds 1 second
        print(f"Caching standard mapdata.")
        cache.set(f"{category}-{id}-standard",
                  reduced_geometry(mapdata_result) if available_tilesets else mapdata_result)
    else:
        print(f"No need to cache mapdata.")

    return JsonResponse(mapdata_result, safe=False, json_dumps_params={'ensure_ascii': False})


def buffer_extent(extent, buffer_distance=0.1):
    return Polygon.from_bbox(extent).buffer(buffer_distance).extent if extent else None


def mapdata_dataset(id, task_id=None, chunk_size=1000):
    ds = get_object_or_404(Dataset, pk=id)

    # Initialize Redis key if task_id is provided
    if task_id:
        redis_client = get_redis_client()
        redis_client.hset(task_id, 'mapdata_start_time', timezone.now().isoformat())
        redis_client.hset(task_id, 'queued_features', ds.numrows)

    features = []
    redis_batch_size = 100  # Define batch size for Redis updates

    # Initialize extent to None, will be updated with actual values
    extent_polygon = None

    # Fetch places in chunks to avoid hitting the database in one go
    places_qs = ds.places.values('id', 'title', 'fclasses', 'review_wd', 'review_tgn', 'review_whg', 'minmax').order_by(
        'id')
    place_iterator = iter(places_qs)
    index = 0

    while True:
        chunk = list(islice(place_iterator, chunk_size))
        if not chunk:
            break

        # Fetch geometries for the current chunk of places
        place_ids = [place['id'] for place in chunk]
        geometries = PlaceGeom.objects.filter(place_id__in=place_ids).only('jsonb', 'geom')

        # Organize geometries by place_id for efficient lookup
        geom_map = {}
        for geom in geometries:
            geom_map.setdefault(geom.place_id, []).append(geom.jsonb)

            # Update the extent dynamically
            if geom.geom and not geom.geom.empty:
                geom_extent = geom.geom.extent  # Returns (xmin, ymin, xmax, ymax)
                geom_bbox = Polygon.from_bbox(geom_extent)
                extent_polygon = geom_bbox if extent_polygon is None else extent_polygon.union(geom_bbox)

        for place in chunk:
            geom_list = geom_map.get(place['id'], [])
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
                "id": index  # Required for MapLibre conditional styling
            }
            features.append(feature)

            # Batch Redis updates for better performance
            if task_id and (index + 1) % redis_batch_size == 0:
                redis_client.hincrby(task_id, 'queued_features', -redis_batch_size)

            index += 1

    # Final Redis update for any remaining items
    if task_id:
        redis_client.hincrby(task_id, 'queued_features', -(index % redis_batch_size))

    # Convert the final extent polygon to a tuple in the format (xmin, ymin, xmax, ymax)
    final_extent = extent_polygon.extent if extent_polygon else None
    buffered_extent = buffer_extent(final_extent) if final_extent else None

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


# def mapdata_dataset(id, task_id=None):
#     ds = get_object_or_404(Dataset, pk=id)
#
#     places = ds.places.prefetch_related(
#         Prefetch('geoms', queryset=PlaceGeom.objects.only('jsonb'))
#     ).values('id', 'title', 'fclasses', 'review_wd', 'review_tgn', 'review_whg', 'minmax').order_by('id')
#
#     extent = buffer_extent(ds.places.aggregate(Extent('geoms__geom')).get('geoms__geom__extent'))
#
#     # Initialize Redis key if task_id is provided
#     if task_id:
#         redis_client = get_redis_client()
#         redis_client.hset(task_id, 'mapdata_start_time', timezone.now().isoformat())
#         redis_client.hset(task_id, 'queued_features', ds.numrows)
#
#     features = []
#     for index, place in enumerate(places):
#         geometries = place.geoms.all()
#         feature = {
#             "type": "Feature",
#             "properties": {
#                 "pid": place.id,
#                 "title": place.title,
#                 "fclasses": place.fclasses,
#                 "review_wd": place.review_wd,
#                 "review_tgn": place.review_tgn,
#                 "review_whg": place.review_whg,
#                 "min": "null" if place.minmax is None or place.minmax[0] is None else place.minmax[0],
#                 "max": "null" if place.minmax is None or place.minmax[1] is None else place.minmax[1],
#             },
#             "geometry": geometries[0].jsonb if len(geometries) == 1
#             else (
#                 None if len(geometries) == 0
#                 else {
#                     "type": "GeometryCollection",
#                     "geometries": [geo.jsonb for geo in geometries]
#                 }
#             ),
#             "id": index  # Required for MapLibre conditional styling
#         }
#         features.append(feature)
#
#         if task_id:
#             redis_client.hincrby(task_id, 'queued_features', -1)
#
#     return {
#         "title": ds.title,
#         "contributors": ds.contributors,
#         "citation": ds.citation,
#         "creator": ds.creator,
#         "minmax": ds.minmax,
#         "extent": extent,
#         "type": "FeatureCollection",
#         "features": features,
#     }


def mapdata_collection(id):
    collection = get_object_or_404(Collection, id=id)

    if collection.collection_class == 'place':
        traces_with_place_ids = collection.traces.filter(archived=False).annotate(annotated_place_id=F('place__id'))
        unique_place_ids = traces_with_place_ids.values_list('annotated_place_id', flat=True).distinct()
        collection_places_all = Place.objects.filter(id__in=unique_place_ids)
    else:  # collection.collection_class == 'dataset'
        collection_places_all = collection.places_all

    extent = buffer_extent(list(collection_places_all.aggregate(Extent('geoms__geom')).values())[0])

    feature_collection = {
        "title": collection.title,
        "creator": collection.creator,
        "type": "FeatureCollection",
        "features": [],
        "extent": extent,
    }

    if collection.collection_class == 'place':
        return mapdata_collection_place(collection, feature_collection)
    else:  # collection.collection_class == 'dataset'
        return mapdata_collection_dataset(collection, collection_places_all, feature_collection)


def mapdata_collection_place(collection, feature_collection):
    traces = collection.traces.filter(archived=False).select_related('place')
    reduce_geometry = any(facet.get("trail") for facet in collection.vis_parameters.values())

    feature_collection["relations"] = collection.rel_keywords

    for index, trace in enumerate(traces):
        place = trace.place
        first_anno_sequence = place.annos.first().sequence if place.annos.exists() else None
        reference_place = place.matches[0] if trace.include_matches and place.matches else place

        if reference_place.geoms.exists():
            unioned_geometry = reference_place.geoms.aggregate(union=Union('geom'))['union']
            if unioned_geometry:
                try:
                    centroid = unioned_geometry.centroid if reduce_geometry else None
                    geometry_collection = json.loads(
                        GeometryCollection(centroid if centroid else unioned_geometry).geojson)
                except (TypeError, ValueError) as e:
                    print(f"Trying alternative geometry collection tranformation for place {place.id}: {e}",
                          unioned_geometry)
                    geometry_collection = json.loads(
                        GeometryCollection(centroid if centroid else list(unioned_geometry)).geojson)
        else:
            geometry_collection = None

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


def mapdata_collection_dataset(collection, collection_places_all, feature_collection):
    '''
    Construct families of matched places within collection
    '''

    close_matches = list(CloseMatch.objects.filter(
        Q(place_a__in=collection_places_all) & Q(place_b__in=collection_places_all)
    ).values_list('place_a_id', 'place_b_id'))
    # close_matches = list( CloseMatch.objects.filter(Q(place_a__in=cpa) & Q(place_b__in=cpa)).values_list('place_a_id', 'place_b_id') )
    print(close_matches)

    # Create a graph if there are close matches, otherwise, an empty graph
    G = nx.Graph(close_matches) if close_matches else nx.Graph()

    families = list(nx.connected_components(G))

    # Start places list with places that have no family connections
    unmatched_places = collection_places_all.exclude(id__in=G.nodes).prefetch_related('geoms').order_by('id')
    # unmatched_places = cpa.exclude(id__in=G.nodes).prefetch_related('geoms').order_by('id')

    print(
        f"Collection {collection.id}: {collection_places_all.count()} places sorted into {len(families)} families and {len(unmatched_places)} unmatched.")

    # print(f"Collection {collection.id}: {cpa.count()} places sorted into {len(families)} families and {len(unmatched_places)} unmatched.")

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
                    print(f"Trying alternative geometry collection tranformation for place {place.id}: {e}",
                          unioned_geometry)
                    geometry_collection = json.loads(GeometryCollection(list(unioned_geometry)).geojson)
        place_min, place_max = place.minmax or (None, None)
        return {
            "id": str(place.id),  # Ensure ID is a string
            "src_id": [place.src_id] if isinstance(place.src_id, int) else place.src_id,
            "title": place.title,
            "fclasses": sorted(set(fc for fc in place.fclasses if fc)) if place.fclasses else [],
            "ccodes": place.ccodes,
            "min": "null" if place_min is None else place_min,
            "max": "null" if place_max is None else place_max,
            "seq": None,
            "geometry": geometry_collection
        }

    # Aggregate information for unmatched places
    places_info = [aggregate_place_info(place) for place in unmatched_places]

    # Aggregate information for family places
    for family in families:
        family_members = Place.objects.filter(id__in=family)
        family_place_geoms = PlaceGeom.objects.filter(place_id__in=family).select_related('place')

        # Create a family place as a pseudo-place object
        family_place = type('FamilyPlace', (object,), {})()
        family_place.id = "-".join(str(place_id) for place_id in sorted(family))
        family_place.src_id = sorted(list(family_members.values_list('src_id', flat=True)))
        family_place.title = "|".join(set(family_members.values_list('title', flat=True)))
        family_place.ccodes = sorted(list(set(chain.from_iterable(family_members.values_list('ccodes', flat=True)))))
        # family_place.fclasses = sorted(list(set(chain.from_iterable(family_members.values_list('fclasses', flat=True)))))
        # family_place.fclasses = sorted(set(filter(None, family_members.values_list('fclasses', flat=True))))
        family_place.fclasses = sorted(
            set(chain.from_iterable(filter(None, family_members.values_list('fclasses', flat=True)))))
        family_place.minmax = [
            min(filter(None, family_members.values_list('minmax__0', flat=True)), default=None),
            max(filter(None, family_members.values_list('minmax__1', flat=True)), default=None)
        ]
        family_place.geoms = family_place_geoms
        family_place.seq = None

        family_info = aggregate_place_info(family_place)
        places_info.append(family_info)
        print(f"Aggregated places {family_info['id']}")

    # Sort places by ID (ensure all IDs are strings)
    places_info.sort(key=lambda x: x['id'])
    places_info = [{'pid': place_info.pop('id'), **place_info} for place_info in places_info]

    # Add places to the feature collection
    for index, place_info in enumerate(places_info):
        feature = {
            "type": "Feature",
            "geometry": place_info.pop('geometry'),
            "properties": place_info,
            "id": index  # Required for MapLibre conditional styling
        }
        feature_collection["features"].append(feature)

    # Calculate min-max values
    min_max_values = [(float(place_info["min"]), float(place_info["max"])) for place_info in places_info if
                      place_info["min"] != "null" and place_info["max"] != "null"]
    feature_collection["minmax"] = [str(min(min_max_values)), str(max(min_max_values))] if min_max_values else [None,
                                                                                                                None]

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
