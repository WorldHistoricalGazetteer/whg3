import json
from datetime import datetime

from areas.models import Area
from whg import settings

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


def make_candidate(hit, query_text, max_score):
    src = hit["_source"]
    name = get_canonical_name(src, hit["_id"])
    alt_names = get_alternative_names(src, name)
    score = normalize_score(hit["_score"], max_score)
    is_exact = name.lower() == query_text.lower()
    return {
        "id": hit.get("whg_id") or str(src.get("place_id") or hit["_id"]),
        "name": name,
        "score": score,
        "match": is_exact,
        "alt_names": alt_names
    }


def build_es_query(params, size=100):
    qstr = params.get("qstr")
    fields = ["title^3", "names.toponym", "searchy"]

    # Search mode handling (default, starts, in, fuzzy)
    search_mode = params.get("mode", "default")
    if search_mode == "starts":
        search_query = {"bool": {"should": [{"prefix": {field: qstr}} for field in fields]}}
    elif search_mode == "in":
        search_query = {"bool": {"should": [{"wildcard": {field: f"*{qstr}*"}} for field in fields]}}
    elif search_mode == "fuzzy":
        search_query = {"multi_match": {"query": qstr, "fields": fields, "fuzziness": 2}}
    else:
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


def es_search(index="whg,pub", query_text=None, ids=None, size=100, params=None):
    if not query_text and not ids:
        return []

    if ids:
        body = {"query": {"ids": {"values": ids}}, "_source": True, "size": len(ids)}
    else:
        params = params or {}
        params["qstr"] = query_text
        body = build_es_query(params, size=size)

    resp = es.search(index=index, body=body)
    return resp.get("hits", {}).get("hits", [])


def extract_alt_names(src):
    canonical = get_canonical_name(src, fallback_id=src.get("place_id", "unknown"))
    return get_alternative_names(src, canonical)


def extract_temporal_range(src):
    start, end = None, None
    if "minmax" in src:
        start = src["minmax"].get("gte")
        end = src["minmax"].get("lte")
    return {"start": start, "end": end}


def extract_dataset(src):
    return src.get("dataset")


def extract_ccodes(src):
    return src.get("ccodes", [])


def format_extend_row(hit, requested_props, features=None):
    src = hit["_source"]
    cells = {}

    for prop in requested_props:
        if prop == "whg:alt_names":
            cells[prop] = {"type": "string[]", "value": extract_alt_names(src)}
        elif prop == "whg:temporalRange":
            cells[prop] = {"type": "range", "value": extract_temporal_range(src)}
        elif prop == "whg:dataset":
            cells[prop] = {"type": "string", "value": extract_dataset(src)}
        elif prop == "whg:ccodes":
            cells[prop] = {"type": "string[]", "value": extract_ccodes(src)}
        elif prop == "whg:geometry" and features is not None:
            geojson = geoms_to_geojson(src)
            if geojson:
                features.extend(geojson["features"])
            # Optionally: still add per-row geometry reference if desired
            cells[prop] = {"type": "geojson-ref", "value": True}

    return {
        "id": hit.get("whg_id") or str(src.get("place_id") or hit["_id"]),
        "cells": cells
    }
