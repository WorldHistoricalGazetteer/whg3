# /api/reconcile_helpers.py

import json
import logging
import os
from datetime import datetime

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from api.serializers import PlaceSerializer
from areas.models import Area
from whg import settings

logger = logging.getLogger('reconciliation')

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

    # handle unlocated (default: true)
    unlocated = params.get("unlocated")
    if unlocated in [False, "false", "False", "0"]:  # explicitly false
        q["query"]["bool"]["must"].append({"exists": {"field": "geoms.location"}})

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

        if pid == "whg:id_short":
            row[pid] = [{"str": f"https://whgazetteer.org/place/{place.id}"}]

        elif pid == "whg:id_object":
            row[pid] = [{"str": json.dumps({
                "id": f"https://whgazetteer.org/place/{place.id}",
                "label": data.get("title", "")
            })}]

        elif pid == "whg:names_canonical":
            # Get preferred name or first name
            names = data.get("names", [])
            canonical = next((n["toponym"] for n in names if n.get("status") == "preferred"),
                             names[0]["toponym"] if names else data.get("title", ""))
            row[pid] = [{"str": canonical}] if canonical else []

        elif pid == "whg:names_array":
            row[pid] = [{"str": json.dumps(data.get("names", []))}]

        elif pid == "whg:names_summary":
            row[pid] = [{"str": n["toponym"]} for n in data.get("names", [])]

        elif pid == "whg:geometry_wkt":
            row[pid] = [{"str": g.get("geowkt")} for g in data.get("geoms", []) if g.get("geowkt")]

        elif pid == "whg:geometry_geojson":
            row[pid] = [{"str": json.dumps(g.get("geojson"))} for g in data.get("geoms", []) if g.get("geojson")]

        elif pid == "whg:geometry_centroid":
            geoms = data.get("geoms", [])
            if geoms and geoms[0].get("centroid"):
                centroid = geoms[0]["centroid"]
                row[pid] = [{"str": json.dumps({"lat": centroid[1], "lng": centroid[0]})}]
            else:
                row[pid] = []

        elif pid == "whg:geometry_bbox":
            geoms = data.get("geoms", [])
            if geoms and geoms[0].get("bbox"):
                row[pid] = [{"str": json.dumps(geoms[0]["bbox"])}]
            else:
                row[pid] = []

        elif pid == "whg:temporal":
            # Modern timespan objects
            timespans = []
            for when in data.get("whens", []):
                timespan = {}
                if when.get("begin"):
                    timespan["begin"] = when["begin"]
                if when.get("end"):
                    timespan["end"] = when["end"]
                if when.get("note"):
                    timespan["note"] = when["note"]
                if timespan:
                    timespans.append(timespan)
            row[pid] = [{"str": json.dumps(timespans)}] if timespans else []

        elif pid == "whg:temporal_legacy":
            # Simple string ranges for backwards compatibility
            legacy_ranges = []
            for when in data.get("whens", []):
                if when.get("minmax"):
                    legacy_ranges.append(f"{when['minmax'][0]}-{when['minmax'][1]}")
            row[pid] = [{"str": r} for r in legacy_ranges]

        elif pid == "whg:countries_codes":
            row[pid] = [{"str": c} for c in data.get("ccodes", [])]

        elif pid == "whg:countries_objects":
            countries = []
            for code in data.get("ccodes", []):
                countries.append({
                    "code": code,
                    "uri": f"http://id.loc.gov/vocabulary/iso3166/{code.lower()}",
                    "label": code  # You might want to map this to full country names
                })
            row[pid] = [{"str": json.dumps(countries)}] if countries else []

        elif pid == "whg:classes_codes":
            row[pid] = [{"str": fc} for fc in data.get("fclasses", [])]

        elif pid == "whg:classes_objects":
            # Map feature class codes to objects with labels
            fclass_map = {
                "A": {"code": "A", "label": "Administrative boundary",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#A"},
                "H": {"code": "H", "label": "Hydrographic",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#H"},
                "L": {"code": "L", "label": "Area",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#L"},
                "P": {"code": "P", "label": "Populated place",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#P"},
                "R": {"code": "R", "label": "Road / Railroad",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#R"},
                "S": {"code": "S", "label": "Spot / Building / Farm",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#S"},
                "T": {"code": "T", "label": "Hypsographic",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#T"},
                "U": {"code": "U", "label": "Undersea",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#U"},
                "V": {"code": "V", "label": "Vegetation",
                      "reference": "https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html#V"}
            }
            classes = [fclass_map.get(fc, {"code": fc, "label": "Unknown", "reference": ""})
                       for fc in data.get("fclasses", []) if fc in fclass_map]
            row[pid] = [{"str": json.dumps(classes)}] if classes else []

        elif pid == "whg:types_objects":
            row[pid] = [{"str": json.dumps(data.get("types", []))}]

        elif pid == "whg:dataset":
            dataset_info = data.get("dataset")
            if dataset_info:
                row[pid] = [{"str": json.dumps(dataset_info)}]
            else:
                row[pid] = []

        elif pid == "whg:lpf_feature":
            lpf_feature = build_lpf_feature(place, data)
            row[pid] = [{"str": json.dumps(lpf_feature)}] if lpf_feature else []

        else:
            # Unknown property ID
            row[pid] = []

    return row


def build_lpf_feature(place, serialized_data):
    """
    Build a complete Linked Places Format GeoJSON Feature
    TODO: This is a placeholder - augment according to exact LPF structure
    """
    lpf_feature = {
        "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
        "type": "Feature",
        "properties": {
            "id": str(place.id),
            "title": serialized_data.get("title", ""),
            "ccodes": serialized_data.get("ccodes", [])
        }
    }

    # Add geometry if available
    geoms = serialized_data.get("geoms", [])
    if geoms and geoms[0].get("geojson"):
        lpf_feature["geometry"] = geoms[0]["geojson"]

    # Add names
    names = serialized_data.get("names", [])
    if names:
        lpf_feature["properties"]["names"] = names

    # Add temporal data
    whens = serialized_data.get("whens", [])
    if whens:
        lpf_feature["properties"]["when"] = whens

    # Add types
    types = serialized_data.get("types", [])
    if types:
        lpf_feature["properties"]["types"] = types

    return lpf_feature


@extend_schema_serializer(component_name=None)
class ReconciliationRequestSerializer(serializers.Serializer):
    queries = serializers.DictField(
        required=False,
        child=serializers.DictField()
    )
    extend = serializers.DictField(
        required=False,
    )


def get_propose_properties(schema_file):
    """
    Parses a WHG schema from a local file and constructs the PROPOSE_PROPERTIES list.

    Args:
        schema_file (str): The local file path to the WHG schema.

    Returns:
        list: A list of dictionaries for reconciliation API properties.
    """
    import json

    if not os.path.exists(schema_file):
        logger.error(f"Schema file not found at: {schema_file}")
        return []

    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON from {schema_file}: {e}")
        return []

    propose_properties = []

    # Iterate through the @graph array
    for item in schema.get('@graph', []):
        if item.get('@type') == 'rdf:Property':
            # Check for whg:apiView
            api_views = item.get('whg:apiView', [])

            # Handle both single object and array of objects
            if isinstance(api_views, dict):
                api_views = [api_views]

            for view in api_views:
                if isinstance(view, dict) and all(k in view for k in ['id', 'name', 'description']):
                    propose_properties.append({
                        "id": view['id'],
                        "name": view['name'],
                        "description": view['description'],
                        "type": "string"
                    })

    # Add special properties
    propose_properties.append({
        "id": "whg:lpf_feature",
        "name": "Linked Places Format Feature",
        "description": "Complete place record as a Linked Places Format GeoJSON Feature with full properties, names, geometry, and links",
        "type": "string"
    })

    logger.debug(f"Generated {len(propose_properties)} propose properties via JSON parsing")
    return propose_properties
