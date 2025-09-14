# whg/api/reconcile.py

"""
WHG Gazetteer Reconciliation API

Provides endpoints for place reconciliation and property extension according to Reconciliation Service API v0.2.
Supports POST requests to /reconcile/ to retrieve candidate places with canonical names, alternative names,
normalized match scores, exact match flags, and full GeoJSON geometries.
Also includes /reconcile/extend/propose for suggesting additional properties and /reconcile/extend for computing
property values (currently not implemented). Authentication is via API token or session/CSRF.
Batch requests are supported, and geometries are always included to aid visual disambiguation.

See documentation: https://docs.whgazetteer.org/content/400-Technical.html#api
"""

import json
import os

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from whg import settings
from .models import APIToken, UserAPIProfile

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#api"

# TODO: Correct the following placeholder metadata
SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "WHG Place Reconciliation",
    "identifierSpace": f"{DOMAIN}/place/",
    "schemaSpace": "https://schema.org/",
    "defaultTypes": [
        {"id": "https://schema.org/Place", "name": "Place"}
    ],
    "documentation": DOCS_URL,
    "logo": f"{DOMAIN}/static/images/whg_logo_square.svg",
    "view": {
        "url": f"{DOMAIN}/place/{{id}}"
    },
    "feature_view": {
        "url": f"{DOMAIN}/feature/{{id}}"
    },
    "preview": {
        # TODO: This might use the tileserver image endpoint
        "url": f"{DOMAIN}/preview/{{id}}?bbox={{bbox}}",
        "width": 430,
        "height": 300,
        "status": "not implemented",
        "note": "Preview functionality is not yet supported"
    },
    "suggest": {
        # TODO: Implement suggest endpoints
        "entity": {
            "service_url": f"{DOMAIN}",
            "service_path": "/suggest/entity",
            "status": "not implemented",
            "note": "Entity suggestion is not yet supported"
        },
        "property": {
            "service_url": f"{DOMAIN}",
            "service_path": "/suggest/property",
            "status": "not implemented",
            "note": "Property suggestion is not yet supported"
        }
    },
    "extend": {
        "propose_properties": {
            "service_url": f"{DOMAIN}",
            "service_path": "/reconcile/extend/propose"
        }
    },
    "batch_size": 50,
    "authentication": {
        "type": "api_token",
        "name": "Authorization",
        "in": "header",
    }
}

# TODO: Replace ElasticSearch with Vespa backend when ready
es = settings.ES_CONN


def json_error(message, status=400):
    return JsonResponse({"error": f"{message} See documentation: {DOCS_URL}"}, status=status)


def authenticate_request(request):
    """
    Authenticate either via:
    1. Authorization: Bearer <token>
    2. CSRF/session (browser-originated)

    Returns:
        (bool, dict|None) -- True and None if authenticated,
                              False and error dict if denied.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth.split(" ", 1)[1]
        try:
            token = APIToken.objects.select_related("user").get(key=key)
            request.user = token.user

            # Ensure UserAPIProfile exists
            profile, _ = UserAPIProfile.objects.get_or_create(user=token.user)

            # Increment usage
            profile.increment_usage()

            # Check daily limit
            if profile.daily_limit and profile.daily_count > profile.daily_limit:
                return False, {
                    "error": f"Daily API limit ({profile.daily_limit} calls) exceeded",
                }

            # Update token last_used
            token.last_used = timezone.now()
            token.save(update_fields=['last_used'])

            return True, None

        except APIToken.DoesNotExist:
            return False, {"error": "Invalid API token"}

    # CSRF/session mode
    if request.user.is_authenticated or request.user.is_anonymous:
        from django.middleware.csrf import get_token
        try:
            get_token(request)  # validate CSRF
            return True, None
        except Exception:
            return False, {"error": "Invalid CSRF token"}

    return False, {"error": "Authentication required"}


@method_decorator(csrf_exempt, name="dispatch")
class ReconciliationView(View):
    # TODO: Add appropriate docstring for Swagger/OpenAPI
    # TODO: Update documentation at DOCS_URL

    def get(self, request, *args, **kwargs):
        return JsonResponse(SERVICE_METADATA)

    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = json.loads(request.body)
            queries = payload.get("queries", {})
        except (json.JSONDecodeError, AttributeError):
            return json_error("Invalid JSON payload")

        if not queries:
            return json_error("Missing 'queries' parameter")

        # Enforce batch size limit
        if len(queries) > SERVICE_METADATA.get("batch_size", 50):
            return json_error(f"Batch size exceeds limit of {SERVICE_METADATA['batch_size']}", status=413)

        results = {}
        for key, q in queries.items():
            query_text = q.get("query")
            if not query_text:
                results[key] = {"result": []}  # empty result if no query
                continue

            results[key] = {
                "result": reconcile_place_es(query_text)
            }

        return JsonResponse(results)


@method_decorator(csrf_exempt, name="dispatch")
class ExtendProposeView(View):
    """
    Endpoint for /reconcile/extend/propose
    Returns a list of suggested properties or enhancements for a set of candidate places.
    """

    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        return JsonResponse({
            "properties": [
                {"id": "whg:geometry", "name": "Geometry (GeoJSON)"},
                {"id": "whg:alt_names", "name": "Alternative names"},
                {"id": "whg:temporalRange", "name": "Temporal range (years)"},
                {"id": "whg:dataset", "name": "Source dataset"},
                {"id": "whg:ccodes", "name": "Country codes"},
            ]
        })

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class ExtendView(View):
    """
    Endpoint for /reconcile/extend
    Returns property values for a set of candidate place IDs.
    Expects POST JSON payload:
    {
        "ids": ["2487384", "12345"],
        "properties": ["whg:geometry", "whg:alt_names", "whg:temporalRange"]
    }
    """

    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = json.loads(request.body)
            candidate_ids = payload.get("ids", [])
            requested_props = payload.get("properties", [])
        except Exception:
            return json_error("Invalid JSON payload")

        if not candidate_ids:
            return JsonResponse({"rows": []})

        # Query Elastic for all candidate IDs
        body = {
            "query": {
                "ids": {"values": candidate_ids}
            },
            "_source": True,
            "size": len(candidate_ids)
        }
        resp = es.search(index="whg,pub", body=body)
        hits = resp.get("hits", {}).get("hits", [])

        rows = []

        for hit in hits:
            src = hit["_source"]
            cells = {}

            if "whg:alt_names" in requested_props:
                alt_names = []
                if src.get("names"):
                    alt_names = [n["toponym"] for n in src["names"]]
                alt_names += [s for s in src.get("searchy", []) if s not in alt_names]
                cells["whg:alt_names"] = {"type": "string[]", "value": alt_names}

            if "whg:temporalRange" in requested_props:
                start, end = None, None
                if "minmax" in src:
                    start = src["minmax"].get("gte")
                    end = src["minmax"].get("lte")
                cells["whg:temporalRange"] = {"type": "range", "value": {"start": start, "end": end}}

            if "whg:dataset" in requested_props:
                cells["whg:dataset"] = {"type": "string", "value": src.get("dataset")}

            if "whg:ccodes" in requested_props:
                cells["whg:ccodes"] = {"type": "string[]", "value": src.get("ccodes", [])}

            rows.append({
                "id": hit.get("whg_id") or str(src.get("place_id") or hit["_id"]),
                "cells": cells
            })

        return JsonResponse({"rows": rows})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class SuggestView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Suggest functionality is not yet implemented. See documentation: " + DOCS_URL
        }, status=501)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


def reconcile_place_es(query_text, index="whg,pub", size=10):
    """
    Reconcile a place name using ElasticSearch only.
    Returns a list of dicts: id, name, score, match, alt_names.
    """
    if not query_text:
        return []

    # Elastic query combining exact match boost + fuzzy
    body = {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {"match_phrase": {"title.keyword": {"query": query_text, "boost": 3}}},
                    {"match": {"searchy": {"query": query_text, "fuzziness": "AUTO"}}}
                ]
            }
        }
    }

    resp = es.search(index=index, body=body)
    hits = resp.get("hits", {}).get("hits", [])

    if not hits:
        return []

    max_score = hits[0]["_score"] if hits else 1.0  # prevent division by zero
    results = []

    for hit in hits:
        src = hit["_source"]

        # Canonical name
        if src.get("title"):
            name = src["title"]
        elif src.get("names"):
            name = src["names"][0]["toponym"]
        elif src.get("searchy"):
            name = src["searchy"][0]
        else:
            name = f"Unknown ({hit['_id']})"

        # Alternative names
        alt_names = []
        if src.get("names"):
            alt_names = [n["toponym"] for n in src["names"] if n.get("toponym") and n["toponym"] != name]
        # Include searchy entries that are not already in alt_names or canonical name
        alt_names += [s for s in src.get("searchy", []) if s not in alt_names and s != name]

        is_exact = name.lower() == query_text.lower()

        # normalize score 0-100 relative to top hit
        raw_score = hit["_score"]
        score = int((raw_score / max_score) * 100)

        # Convert geoms to GeoJSON FeatureCollection
        features = []
        for geom in src.get("geoms", []):
            if "location" in geom:
                features.append({
                    "type": "Feature",
                    "geometry": geom["location"],
                    "properties": {}
                })
            else:
                # If it's a polygon or other geometry
                features.append({
                    "type": "Feature",
                    "geometry": geom,  # assume already GeoJSON-compliant
                    "properties": {}
                })

        geojson = {"type": "FeatureCollection", "features": features} if features else None

        results.append({
            "id": hit.get("whg_id") or str(src.get("place_id") or hit["_id"]),
            "name": name,
            "score": score,
            "match": is_exact,
            "geojson": geojson,
            "alt_names": alt_names
        })

    return results
