# /api/reconcile_helpers.py

import json
from datetime import datetime

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from rest_framework import serializers

from api.serializers import PlaceSerializer
from areas.models import Area
from whg import settings

ELASTIC_INDICES = "whg,pub,wdgn"  # or options from "whg,pub,wdgn"

# TODO: Replace ElasticSearch with Vespa backend when ready
es = settings.ES_CONN


def get_canonical_name(src, fallback_id):
    if src.get("title"):
        return src["title"]
    elif src.get("names"):
        return src["names"][0]["toponym"]
    elif src.get("searchy"):
        return src["searchy"][0]
    else:
        return f"Unknown ({fallback_id})"


def get_alternative_names(src, canonical_name):
    alt_names = []
    if src.get("names"):
        alt_names = [n["toponym"] for n in src["names"] if n.get("toponym") and n["toponym"] != canonical_name]
    alt_names += [s for s in src.get("searchy", []) if s not in alt_names and s != canonical_name]
    return alt_names


def normalize_score(raw_score, max_score):
    return int((raw_score / max_score) * 100) if max_score else 0


def geoms_to_geojson(src):
    place_id = str(src.get("place_id") or "unknown")
    name = get_canonical_name(src, place_id)
    features = []
    for geom in src.get("geoms", []):
        geometry = geom.get("location", geom)
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": place_id,
                "name": name,
            }
        })
    return {"type": "FeatureCollection", "features": features} if features else None


def make_candidate(hit, query_text, max_score, schema_space):
    src = hit["_source"]
    name = get_canonical_name(src, hit["_id"])
    alt_names = get_alternative_names(src, name)
    score = normalize_score(hit["_score"], max_score)
    is_exact = name.lower() == query_text.lower()
    return {
        "id": str(src.get("place_id")),  # or hit.get("whg_id") or hit["_id"]),
        "name": name,
        "score": score,
        "match": is_exact,
        "alt_names": alt_names,
        "type": [
            {
                "id": schema_space + "#Place",
                "name": "Place"
            }
        ]
    }


def build_es_query(params, size=100):
    qstr = params.get("qstr")
    fields = ["title^3", "names.toponym", "searchy"]

    # Search mode handling (default, starts, in, fuzzy)
    search_mode = params.get("mode", "fuzzy")

    # Handle "prefix|fuzziness" mode
    if "|" in search_mode:
        mode_parts = search_mode.split("|")
        if len(mode_parts) != 2:
            raise ValueError(f"Invalid fuzzy mode: {search_mode}. Expected format 'prefix|fuzziness'.")
        prefix_length, fuzziness = mode_parts
        if prefix_length.isdigit() and (
                fuzziness == "AUTO" or (fuzziness.isdigit() and int(fuzziness) >= 0 and int(fuzziness) <= 2)):
            search_query = {
                "multi_match": {
                    "query": qstr,
                    "fields": fields,
                    "type": "best_fields",
                    "fuzziness": fuzziness if fuzziness == "AUTO" else int(fuzziness),
                    "prefix_length": int(prefix_length)
                }
            }
        else:
            raise ValueError(f"Invalid fuzzy mode: {search_mode}")
    elif search_mode == "starts":
        search_query = {"bool": {"should": [{"prefix": {field: qstr}} for field in fields]}}
    elif search_mode == "in":
        search_query = {"bool": {"should": [{"wildcard": {field: f"*{qstr}*"}} for field in fields]}}
    elif search_mode == "fuzzy":
        search_query = {
            "multi_match": {
                "query": qstr,
                "fields": fields,
                "type": "best_fields",
                "fuzziness": "AUTO",
                "prefix_length": 2
            }
        }
    else:  # "exact" or any other
        search_query = {"multi_match": {"query": qstr, "fields": fields}}

    q = {
        "size": size,
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "whg_id"}},
                    search_query
                ]
            }
        }
    }

    # fclasses
    fclasses = params.get("fclasses")
    if fclasses:
        if isinstance(fclasses, str):
            fclasses = fclasses.split(",")
        fclasses.append("X")
        q["query"]["bool"]["must"].append({"terms": {"fclasses": fclasses}})

    # temporal
    if params.get("temporal"):
        current_year = datetime.now().year
        start_year = str(params.get("start")) if params.get("start") else None
        end_year = str(params.get("end", current_year))
        if start_year:
            timespan_filter = {"range": {"timespans": {"gte": start_year, "lte": end_year}}}
            if params.get("undated"):
                q["query"]["bool"]["must"].append({
                    "bool": {"should": [timespan_filter, {"bool": {"must_not": {"exists": {"field": "timespans"}}}}]}
                })
            else:
                q["query"]["bool"]["must"].append(timespan_filter)

    # countries
    countries = params.get("countries")
    if countries:
        if isinstance(countries, str):
            countries = json.loads(countries)
        q["query"]["bool"]["must"].append({"terms": {"ccodes": countries}})

    # spatial filters (bounds + userareas)
    geometry_filters = []

    bounds = params.get("bounds")
    if bounds:
        if isinstance(bounds, str):
            bounds = json.loads(bounds)
        if bounds.get("geometries"):
            for geometry in bounds["geometries"]:
                geometry_filters.append({
                    "geo_shape": {
                        "geoms.location": {
                            "shape": {
                                "type": geometry["type"],
                                "coordinates": geometry["coordinates"]
                            },
                            "relation": "intersects"
                        }
                    }
                })

    userareas = params.get("userareas")
    if userareas:
        for userarea_id in userareas:
            user_area = Area.objects.filter(id=userarea_id).values("geojson").first()
            if user_area:
                geometry_filters.append({
                    "geo_shape": {
                        "geoms.location": {
                            "shape": user_area["geojson"],
                            "relation": "intersects"
                        }
                    }
                })

    if geometry_filters:
        q["query"]["bool"]["must"].append({"bool": {"should": geometry_filters, "minimum_should_match": 1}})

    return q


def es_search(index=ELASTIC_INDICES, query=None, ids=None):
    """
    Execute an Elasticsearch search.

    query: dict from normalise_query_params
    ids: optional list of document IDs to fetch directly
    """

    if ids:
        body = {
            "query": {
                "terms": {
                    "place_id": ids
                }
            },
            "_source": True,
            "size": len(ids),
        }
    elif query:
        params = dict(query["raw"])  # shallow copy
        params["qstr"] = query["query_text"]
        body = build_es_query(params, size=query["size"])
    else:
        return []

    resp = es.search(index=index, body=body)
    return resp.get("hits", {}).get("hits", [])


def format_extend_row(place, properties, request=None):
    """
    Build the property values dict for an OpenRefine extend row.
    - place: Place instance.
    - properties: list of property dicts or strings.
    """
    serializer = PlaceSerializer(place, context={"request": request})
    data = serializer.data

    row = {}
    for prop in properties:
        pid = prop.get("id") if isinstance(prop, dict) else prop

        if pid == "whg:geometry":
            row[pid] = [g["geom"] for g in data.get("geoms", [])]
        elif pid == "whg:alt_names":
            row[pid] = [n["toponym"] for n in data.get("names", [])]
        elif pid == "whg:ccodes":
            row[pid] = data.get("ccodes", [])
        elif pid == "whg:dataset":
            row[pid] = data.get("dataset")
        elif pid == "whg:temporalRange":
            row[pid] = data.get("whens", [])
        else:
            row[pid] = None

    return row



@extend_schema_serializer(
    examples=[
        OpenApiExample(
            name="Basic Reconciliation Request",
            description="Example of reconciling place names",
            value={
                "queries": {
                    "q0": {"query": "Edinburgh", "type": "Place"},
                    "q1": {"query": "Leeds", "type": "Place"}
                }
            }
        ),
        OpenApiExample(
            name="Advanced Spatial Query",
            description="Search with custom fuzziness and with geographic and temporal constraints",
            value={
                "queries": {
                    "q0": {
                        "query": "London",
                        "mode": "3|2",
                        "countries": ["GB"],
                        "start": 1800,
                        "end": 1900,
                        "lat": 51.5074,
                        "lng": -0.1278,
                        "radius": 10,
                        "fclasses": ["P"],
                        "size": 10
                    }
                }
            }
        ),
        OpenApiExample(
            name="Extend Request",
            description="Example of extending places with additional properties",
            value={
                "extend": {
                    "ids": ["Q23436", "Q39121"],
                    "properties": [
                        {"id": "P1082", "name": "population"},
                        {"id": "P625", "name": "coordinate location"}
                    ]
                }
            }
        ),
    ]
)
class ReconciliationRequestSerializer(serializers.Serializer):
    queries = serializers.DictField(
        required=False,
        help_text=(
            "Dictionary of query objects. Each query supports parameters like: "
            "query (string), mode (exact|fuzzy|starts|in), fclasses (array), "
            "start/end (integers), countries (array), bounds/lat/lng/radius (spatial), "
            "dataset (integer), size (integer)."
        ),
        child=serializers.DictField()
    )
    extend = serializers.DictField(
        required=False,
        help_text="Extension request with 'ids' array and 'properties' array"
    )
