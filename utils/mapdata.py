import json
import logging
import time
from collections import defaultdict
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
from shapely.geometry.geo import shape, mapping

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


def round_coords(coords, precision=6):
    """Recursively round coordinates to the specified precision."""
    if isinstance(coords, (float, int)):
        return round(coords, precision)
    elif isinstance(coords, list):
        return [round_coords(item, precision) for item in coords]
    else:
        return coords  # Return other data types as is


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

    maxNoCacheTime = 0.3  # Cache if generation time is greater than this

    refresh = str(refresh).lower() in ['refresh', 'true', '1', 'yes']
    ds_id = f"{category}_{id}"
    logger.debug(f"Mapdata requested for {ds_id} (refresh={refresh}).")

    # Check if cached data exists and return it if found
    if not refresh:
        cached_data = cache.get(ds_id)
        if cached_data is not None:
            logger.debug("Found cached mapdata.")
            return JsonResponse(cached_data, safe=False, json_dumps_params={'ensure_ascii': False})

    cache.delete(ds_id)
    start_time = time.time()

    mapdata = mapdata_dataset(id) if category == "datasets" else mapdata_collection(id)

    ###############################################################################
    ###############################################################################
    # TODO: REMOVE THIS ONCE THE DATASET HAS BEEN RE-PROCESSED
    if id == 838 and category == "datasets":
        for feature in mapdata["features"]:
            geom = feature.get("geometry", {})
            if geom.get("type") == "Polygon" or geom.get("type") == "MultiPolygon":
                geom["granularity"] = 30  # Inject into geometry, not just properties
    ###############################################################################
    ###############################################################################

    grouped = {
        "Table": [],
        "MultiDataset": [],
        "Point": [],
        "LineString": [],
        "Polygon": [],
        "Granular": []
    }
    multi_relations = set()
    default_group = grouped["Point"]

    # Properties to retain for map features
    required_keys = {"min", "max", "relation"}

    def trim_properties(f, index, g):
        """Return a copy of feature with minimal properties, rounded and validated geometry (or None if invalid)."""
        geometry = None
        if g:
            try:
                # Create a Shapely geometry from the rounded coordinates
                rounded = {
                    "type": g["type"],
                    "coordinates": round_coords(g["coordinates"])
                }

                # Use Shapely to validate
                shapely_geom = shape(rounded)
                if shapely_geom.is_valid:
                    geometry = mapping(shapely_geom)
                    if "granularity" in g:
                        geometry["granularity"] = g["granularity"]
                else:
                    print(f"Invalid geometry at index {index}; replacing with None.")

            except Exception as e:
                print(f"Error processing geometry at index {index}: {e}")
                geometry = None

        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {k: v for k, v in f.get("properties", {}).items() if k in required_keys},
            "id": index
        }

    for index, feature in enumerate(mapdata["features"]):

        geom = feature.get("geometry")
        props = feature.get("properties", {})

        grouped["Table"].append({
            "type": "Feature",
            "geometry": {"type": geom["type"]} if geom and "type" in geom else None,
            "properties": {**props, "dsid": id, "dslabel": mapdata["label"] if "label" in mapdata else None,
                           "ds_id": ds_id, "id": index},
        })

        relation = str(props.get("relation", ""))
        if "|" in relation:
            multi_relations.add(relation)

        if not geom:
            default_group.append(trim_properties(feature, index, None))
            continue

        gtype = geom["type"]
        base_type = gtype.removeprefix("Multi")

        if gtype == "GeometryCollection":
            subgroups = defaultdict(list)
            for subgeom in geom.get("geometries", []):
                subtype = subgeom["type"].removeprefix("Multi")
                if "granularity" in subgeom:
                    grouped["Granular"].append(trim_properties(feature, index, subgeom))
                if subtype in grouped:
                    subgroups[subtype].append(subgeom)

            for subtype, geoms in subgroups.items():
                new_geom = {
                    "type": f"Multi{subtype}" if len(geoms) > 1 else subtype,
                    "coordinates": [g["coordinates"] for g in geoms] if len(geoms) > 1 else geoms[0]["coordinates"],
                }
                grouped[subtype].append(trim_properties(feature, index, new_geom))

        else:
            if "granularity" in geom:
                grouped["Granular"].append(trim_properties(feature, index, geom))
            if base_type in grouped:
                grouped[base_type].append(trim_properties(feature, index, geom))

    mapdata_result = {
        key: ({"features": features} if key in ["table"] else {
            "type": "FeatureCollection", "features": features
        })
        for key, features in {
            "table": grouped["Table"],
            "point": grouped["Point"],
            "line": grouped["LineString"],
            "polygon": grouped["Polygon"],
            "granular": grouped["Granular"],
        }.items()
        if features
    }
    layers = [key for key in mapdata_result.keys() if key != "table"]

    mapdata_result["metadata"] = {
        "id": id,
        "ds_type": category,
        "ds_id": ds_id,
        "label": mapdata.get("label", None),
        "title": mapdata.get("title", None),
        "attribution": attribution_from_csl(json.loads(mapdata.get("citation", None))),
        "layers": layers,
        "modified": mapdata.get("modified", None),
        "min": mapdata["minmax"][0],
        "max": mapdata["minmax"][1],
        "seqmin": mapdata.get("seqmin", None),
        "seqmax": mapdata.get("seqmax", None),
        "num_places": len(mapdata["features"]),
        "bounds": json.loads(mapdata["bounds"].geojson),
        "extent": mapdata["extent"],  # Buffered bounds
        "coordinate_density": mapdata.get("coordinate_density", None),
        "datasets": mapdata.get("datasets", None),
        "relations": mapdata.get("relations", None),
        "multi_relations": list(multi_relations) if multi_relations else [],
        # Default values for visParameters:
        # tabulate: 'initial'|true|false - include sortable table column, 'initial' indicating the initial sort column
        # temporal_control: 'player'|'filter'|null - control to be displayed when sorting on this column
        # trail: true|false - whether to include ant-trail motion indicators on map
        "visParameters": mapdata.get("visParameters",
                                     "{'seq': {'tabulate': false, 'temporal_control': null, 'trail': true}, 'min': {'tabulate': false, 'temporal_control': null, 'trail': true}, 'max': {'tabulate': false, 'temporal_control': null, 'trail': false}}"),
    }

    # logger.debug("Resulting mapdata: %s", mapdata_result)
    # mapdata_result = mapdata

    response_time = time.time() - start_time
    logger.debug(f"Mapdata generation time: {response_time:.2f} seconds")

    if response_time > maxNoCacheTime:
        logger.debug("Caching mapdata.")
        cache.set(ds_id, mapdata_result)
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
    ).values('id', 'src_id', 'title', 'fclasses', 'review_wd', 'review_tgn', 'review_whg', 'minmax').order_by('id')

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
                    "src_id": place['src_id'],
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
                )
            }
            features.append(feature)

            if task_id and (index + 1) % redis_batch_size == 0:
                redis_client.hincrby(task_id, 'queued_features', -redis_batch_size)

            index += 1

    if task_id:
        redis_client.hincrby(task_id, 'queued_features', -(index % redis_batch_size))

    return {
        "title": ds.title,
        "label": ds.label,
        "modified": ds.last_modified_text,
        "contributors": ds.contributors,
        "citation": ds.citation_csl,
        "creator": ds.creator,
        "minmax": ds.minmax,
        "bounds": ds.bbox,
        "extent": buffered_extent,
        "coordinate_density": ds.coordinate_density,
        "visParameters": ds.vis_parameters,
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
        "bounds": collection.bbox,
        "extent": buffered_extent_from_bbox(collection.bbox),
        "coordinate_density": collection.coordinate_density,
        "visParameters": collection.vis_parameters,
        "citation": collection.citation_csl
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

    seq_values = []
    years = []

    for index, trace in enumerate(traces):
        place = places[trace.place.id]
        first_anno_sequence = place.annos.first().sequence if place.annos.exists() else None
        if first_anno_sequence is not None:
            seq_values.append(first_anno_sequence)
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
            "geometry": geometry_collection
        }

        if trace.include_matches and place != reference_place:
            feature["properties"]["geometry_pid"] = reference_place.id

        feature_collection["features"].append(feature)

        # Collect years for minmax calculation
        if feature["properties"]["min"]:
            years.append(feature["properties"]["min"])
        if feature["properties"]["max"]:
            years.append(feature["properties"]["max"])

    if seq_values:
        feature_collection["seqmin"] = min(seq_values)
        feature_collection["seqmax"] = max(seq_values)

    feature_collection["minmax"] = [min(years), max(years)] if years else [None, None]

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
    G = nx.Graph(list(close_matches)) if close_matches else nx.Graph()
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

        family_place.minmax = [
            min(filter(None, family_members.values_list('minmax__0', flat=True)), default=None),
            max(filter(None, family_members.values_list('minmax__1', flat=True)), default=None)
        ]

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
        place_info["relation"] = "|".join(sorted(str(unique_id) for unique_id in unique_ids))

        # Construct the feature object for the collection
        feature = {
            "type": "Feature",
            "geometry": place_info.pop('geometry'),
            "properties": place_info
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

    feature_collection["datasets"] = list(collection.datasets.values("id", "title"))

    return feature_collection


def attribution_from_csl(citation, max_title_length=60):
    """
    Returns a condensed attribution string from a CSL citation dict.
    Format: "Author(s), Year – Title"
    """
    authors = []
    for author in citation.get("author", []):
        if "literal" in author:
            authors.append(author["literal"])
        elif "family" in author:
            initial = author.get("given", "")[:1]
            name = author["family"]
            if initial:
                name += f" {initial}."
            authors.append(name)

    # Format author string
    if not authors:
        author_str = "Unknown"
    elif len(authors) == 1:
        author_str = authors[0]
    elif len(authors) == 2:
        author_str = f"{authors[0]} & {authors[1]}"
    else:
        author_str = f"{authors[0]} et al."

    # Extract year
    try:
        year = citation["issued"]["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        year = "n.d."  # no date

    # Handle title
    title = citation.get("title", "")
    if len(title) > max_title_length:
        title = title[: max_title_length - 1] + "…"

    return f"{author_str}, {year} – {title}" if title else f"{author_str}, {year}"


class MapdataFileBasedCache(FileBasedCache):
    def __init__(self, dir, params):
        super().__init__(dir, params)

    def _cull(self):
        """Override to disable Django's culling mechanism entirely."""
        pass

    # def _cull(self):
    #     """
    #     Custom cull implementation: Remove the smallest cache entries if max_entries is reached.
    #     """
    #     filelist = self._list_cache_files()
    #     num_entries = len(filelist)
    #     if num_entries < self._max_entries:
    #         return  # return early if no culling is required
    #     if self._cull_frequency == 0:
    #         return self.clear()  # Clear the cache when CULL_FREQUENCY = 0
    #
    #     # Sort filelist by file size
    #     filelist.sort(key=lambda x: os.path.getsize(x))
    #
    #     # Delete the smallest entries
    #     num_to_delete = int(num_entries / self._cull_frequency)
    #     for fname in filelist[:num_to_delete]:
    #         self._delete(fname)
