# whg/api/reconcile.py

"""
WHG Gazetteer Reconciliation API

Provides endpoints for place reconciliation and property extension according to Reconciliation Service API v0.2.
Supports POST requests to /reconcile/ to retrieve candidate places with canonical names, alternative names,
normalized match scores, exact match flags, and full GeoJSON geometries.
Also includes /reconcile/extend/propose for suggesting additional properties and /reconcile/extend for computing
property values (currently not implemented). Authentication is via API token or session/CSRF.
Batch requests are supported, and geometries are always included to aid visual disambiguation.

See documentation: https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api
"""

import json
import os

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import APIToken, UserAPIProfile
from .reconcile_helpers import make_candidate, format_extend_row, es_search, geoms_to_geojson

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"

SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "WHG Place Reconciliation",
    "identifierSpace": f"{DOMAIN}/place/",
    # TODO: Change the following two parameters to use custom WHG schema
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
        "entity": {
            "service_url": f"{DOMAIN}",
            "service_path": "/suggest/entity",
            "status": "implemented",
        },
        "property": {
            # TODO: Implement suggest/property endpoint
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
            query_size = q.get("size", 100)
            if not query_text:
                results[key] = {"result": []}  # empty result if no query
                continue

            results[key] = reconcile_place_es(query_text, params=q, size=query_size)

        return JsonResponse(results)


@method_decorator(csrf_exempt, name="dispatch")
class ExtendProposeView(View):

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

        hits = es_search(index="whg,pub", ids=candidate_ids)

        rows = []
        features = []

        for hit in hits:
            row = format_extend_row(hit, requested_props, features)
            rows.append(row)

        response = {"rows": rows}
        if "whg:geometry" in requested_props and features:
            response["geojson"] = {"type": "FeatureCollection", "features": features}

        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class SuggestView(View):
    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = json.loads(request.body)
            query_text = payload.get("query", "")
            limit = int(payload.get("limit", 10))
        except (json.JSONDecodeError, ValueError, TypeError):
            return json_error("Invalid JSON payload or parameters")

        if not query_text:
            return JsonResponse({"result": []})

        # Execute search and build candidates using existing helpers
        hits = es_search(index="whg,pub", query_text=query_text, size=limit)
        if not hits:
            return JsonResponse({"result": []})

        max_score = hits[0]["_score"]
        candidates = [make_candidate(hit, query_text, max_score) for hit in hits]

        return JsonResponse({"result": candidates})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


def reconcile_place_es(query_text, index="whg,pub", size=100, params=None):
    hits = es_search(index=index, query_text=query_text, size=size, params=params)
    if not hits:
        return {"result": [], "geojson": None}

    max_score = hits[0]["_score"]
    results = []
    features = []

    for hit in hits:
        candidate = make_candidate(hit, query_text, max_score)
        results.append(candidate)

        geojson = geoms_to_geojson(hit["_source"])
        if geojson:
            features.extend(geojson["features"])

    return {
        "result": results,
        "geojson": {"type": "FeatureCollection", "features": features} if features else None
    }
