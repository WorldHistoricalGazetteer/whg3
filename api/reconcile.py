# whg/api/reconcile.py

"""
WHG Gazetteer Reconciliation API

Provides endpoints for place reconciliation and property extension according to Reconciliation Service API v0.2.
Supports POST requests to /reconcile/ to retrieve candidate places with canonical names, alternative names,
normalized match scores, exact match flags, and full GeoJSON geometries.
Also includes /reconcile/extend/propose for suggesting additional properties and /reconcile/extend for computing
property values. Authentication is via API token or session/CSRF.
Batch requests are supported.

See documentation: https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api
"""

import json
import logging
import math
import os
from urllib.parse import urlencode

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from geopy.distance import geodesic

from main.choices import FEATURE_CLASSES
from .models import APIToken, UserAPIProfile
from .reconcile_helpers import make_candidate, format_extend_row, es_search

logger = logging.getLogger('reconciliation')

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"
TILESERVER_URL = os.environ.get('TILEBOSS', 'https://tiles.whgazetteer.org').rstrip('/')
MAX_EARTH_RADIUS_KM = math.pi * 6371  # ~20015 km
VALID_FCODES = {fc for fc, _ in FEATURE_CLASSES}

SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "World Historical Gazetteer Place Reconciliation Service",
    "identifierSpace": DOMAIN + "/place/",
    "schemaSpace": DOMAIN + "/static/whg_place_schema.jsonld",
    "defaultTypes": [
        {
            "id": DOMAIN + "/static/whg_place_schema.jsonld#Place",
            "name": "Place"
        }
    ],
    "documentation": DOCS_URL,
    "logo": DOMAIN + "/static/images/whg_logo_80.png",
    "view": {
        "url": DOMAIN + "/places/portal/{{id}}/"
    },
    "feature_view": {
        "url": DOMAIN + "/feature/{{id}}"
    },
    "preview": {
        "url": DOMAIN + "/{{token}}/preview/?id={{id}}",
        "width": 400,
        "height": 300,
    },
    "suggest": {
        "entity": {
            "service_url": DOMAIN + "/{{token}}",
            "service_path": "/suggest/entity",
        },
        "property": {
            "service_url": DOMAIN + "/{{token}}",
            "service_path": "/suggest/property",
        }
    },
    "extend": {
        "propose_properties": {
            "service_url": DOMAIN + "/{{token}}",
            "service_path": "/reconcile/extend/propose"
        }
    },
    "batch_size": 50,
    "authentication": {
        "type": "apiKey",
        "name": "Authorization",
        "in": "header",
    }
}


PROPOSE_PROPERTIES = [
    {"id": "whg:geometry", "name": "Geometry (GeoJSON)", "description": "The geometrical location (GeoJSON) of the place"},
    {"id": "whg:alt_names", "name": "Alternative names", "description": "Alternative names or aliases for the place"},
    {"id": "whg:temporalRange", "name": "Temporal range (years)", "description": "The temporal range(s) associated with the place record"},
    {"id": "whg:dataset", "name": "Source dataset", "description": "The source dataset from which the place record originates"},
    {"id": "whg:ccodes", "name": "Country codes", "description": "The ISO 2-letter country codes associated with the place"},
    {"id": "whg:fclasses", "name": "Feature classes", "description": "The feature classes (e.g., 'A' for administrative regions, 'P' for populated places)"},
    {"id": "whg:types", "name": "Types", "description": "The types or categories associated with the place"},
]


def json_error(message, status=400):
    return JsonResponse({"error": f"{message} See documentation: {DOCS_URL}"}, status=status)


# TODO: Consider using this function to replace part of the current bot-blocking middleware at main.block_user_agents.BlockUserAgentsMiddleware
def authenticate_request(request, token_from_path=None):
    """
    Authenticate either via:
    1. Authorization: Bearer <token>
    2. token extracted from URL path
    3. CSRF/session (browser-originated)
    """
    key = None

    # 1. Check Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth.split(" ", 1)[1]

    # 2. Check token from URL path
    if not key and token_from_path:
        key = token_from_path

    if key:
        try:
            token = APIToken.objects.select_related("user").get(key=key)
            request.user = token.user

            # Ensure UserAPIProfile exists
            profile, _ = UserAPIProfile.objects.get_or_create(user=token.user)
            profile.increment_usage()

            if profile.daily_limit and profile.daily_count > profile.daily_limit:
                return False, {
                    "error": f"Daily API limit ({profile.daily_limit} calls) exceeded",
                }

            token.last_used = timezone.now()
            token.save(update_fields=['last_used'])
            return True, None

        except APIToken.DoesNotExist:
            return False, {"error": "Invalid API token"}

    # 3. CSRF/session mode
    if request.user.is_authenticated or request.user.is_anonymous:
        from django.middleware.csrf import get_token
        try:
            get_token(request)
            return True, None
        except Exception:
            return False, {"error": "Invalid CSRF token"}

    return False, {"error": "Authentication required"}


@method_decorator(csrf_exempt, name="dispatch")
class ReconciliationView(View):
    """
    Reconciliation API endpoint for place name queries.

    **Endpoints:**
    - `GET /reconcile/` : Returns service metadata.
    - `POST /reconcile/` : Accepts one or more queries and returns candidate matches.

    **POST payload format:**
    ```json
    {
        "queries": {
            "q1": {
                "query": "London",
                "mode": "fuzzy",
                "fclasses": ["P"],
                "start": 1200,
                "end": 1600,
                "undated": true,
                "countries": ["GB","US"],
                "bounds": {
                    "geometries": [{
                        "type": "Polygon",
                        "coordinates": [[
                            [-1.0,51.0],
                            [-1.0,52.0],
                            [0.5,52.0],
                            [0.5,51.0],
                            [-1.0,51.0]
                        ]]
                    }]
                },
                "userareas": [1,2],
                "size": 100
            }
        }
    }
    ```

    **Query parameters:**
    - `query` (string): Text search string. Required unless `bounds`, `lat/lng/radius`, or `dataset` filters are present.
    - `mode` (string): Search mode. Options are `"exact"` (multi-match), `"fuzzy"` (default, `"AUTO"` fuzziness, prefix_length=2), `"starts"` (prefix match), or `"in"` (substring/wildcard match). You may also specify a custom fuzzy mode as `"prefix_length|fuzziness"` (e.g., `"2|1"`), where `prefix_length` is the number of initial characters that must match exactly and `fuzziness` is `"AUTO"` or an integer ≤ 2.
    - `fclasses` (array): Feature classes to restrict results.
    - `start`/`end` (int): Temporal filtering years.
    - `undated` (boolean): Include undated results.
    - `countries` (array): ISO 2-letter country codes.
    - `bounds` (object): GeoJSON Polygon to restrict results spatially.
    - `userareas` (array): IDs of server-side stored areas.
    - `lat`/`lng`/`radius` (float): Circle filter for nearby search.
    - `dataset` (int): Restrict to a dataset. # TODO: Allow multiple named datasets such as GeoNames or OSM for either inclusion or exclusion, for example "dataset=geonames,osm" or "dataset=-geonames,-osm".
    - `size` (int): Maximum results per query.

    **Response format:**
    ```json
    {
        "results": {
            "q1": {
                "result": [
                    {
                        "id": "whg:123",
                        "name": "London",
                        "alt": ["Londinium"],
                        "score": 100,
                        "exact": true
                    }
                ],
                "geojson": {
                    "type": "FeatureCollection",
                    "features": [...]
                }
            },
            "messages": [
                "Batch size limit exceeded; processing first 50 queries."
            ]
        }
    }
    ```
    """

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        logger.debug("Reconcile token (path): %s", token)

        metadata = json.loads(json.dumps(SERVICE_METADATA))

        if token:
            def inject_token(obj):
                if isinstance(obj, dict):
                    return {k: inject_token(v) for k, v in obj.items()}
                elif isinstance(obj, str):
                    return obj.replace("{{token}}", token)
                else:
                    return obj

            metadata = inject_token(metadata)

        return JsonResponse(metadata)

    def post(self, request, *args, **kwargs):
        token = kwargs.get("token")
        allowed, auth_error = authenticate_request(request, token_from_path=token)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = parse_request_payload(request, expect_queries=True)
        except ValueError as e:
            return json_error(str(e))

        queries = payload.get("queries", {})
        if not queries:
            return json_error("Missing 'queries' parameter")

        results = process_queries(queries, batch_size=SERVICE_METADATA.get("batch_size", 50))
        return JsonResponse(results)


@method_decorator(csrf_exempt, name="dispatch")
class ExtendProposeView(View):

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        allowed, auth_error = authenticate_request(request, token_from_path=token)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        return JsonResponse({
            "properties": PROPOSE_PROPERTIES
        })

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class ExtendView(View):
    def post(self, request, *args, **kwargs):
        token = kwargs.get("token")
        allowed, auth_error = authenticate_request(request, token_from_path=token)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = parse_request_payload(request)
            candidate_ids = payload.get("ids", [])
            requested_props = payload.get("properties", [])
        except ValueError as e:
            return json_error(str(e))

        if not candidate_ids:
            return JsonResponse({"rows": []})

        hits = es_search_by_ids(candidate_ids)

        rows, features = [], []
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
class SuggestEntityView(View):
    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        allowed, auth_error = authenticate_request(request, token_from_path=token)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        prefix = request.GET.get("prefix", "").strip()
        exact = request.GET.get("exact", "false").lower() == "true"

        # These parameters are passed by OpenRefine but not implemented here as it is unclear how they should affect suggestions
        # spell = request.GET.get("spell", "always")
        # prefixed = request.GET.get("prefixed", "false").lower() == "true"

        if not prefix:
            return JsonResponse({"result": []})

        # Construct search parameters
        raw_params = {
            "query": prefix,
            "size": int(request.GET.get("limit", 10)),
        }
        query = normalise_query_params(raw_params)

        query["mode"] = "starts" if exact else "fuzzy"

        hits = es_search(query=query)
        if not hits:
            return JsonResponse({"result": []})

        max_score = hits[0].get("_score", 1.0)
        candidates = [make_candidate(hit, query["query_text"], max_score) for hit in hits]

        return JsonResponse({"result": candidates})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts GET. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class SuggestPropertyView(View):
    """
    /suggest/property
    Returns suggested property names for entities.
    """

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        allowed, auth_error = authenticate_request(request, token_from_path=token)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            query_text = (request.GET.get("prefix") or request.GET.get("query") or "").strip().lower()
            limit = int(request.GET.get("limit", 10))
        except (ValueError, TypeError):
            return json_error("Invalid query parameters")

        # Filter the global constant PROPOSE_PROPERTIES
        if query_text:
            matches = [prop for prop in PROPOSE_PROPERTIES if query_text in prop['name'].lower()]
        else:
            matches = PROPOSE_PROPERTIES

        return JsonResponse({"result": matches[:limit]})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts GET. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class DummyView(View):
    """
    Dummy endpoint for OpenRefine's legacy search calls.
    Always returns an empty result set.
    """

    _response = JsonResponse({
        "result": [],
        "message": "OpenRefine legacy search call: no results. Use /suggest/entity endpoint instead. See documentation: " + DOCS_URL
    })

    def get(self, request, *args, **kwargs):
        return self._response

    def post(self, request, *args, **kwargs):
        return self._response

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts GET or POST."
        }, status=405)


def parse_request_payload(request, expect_queries: bool = False):
    """
    Parse request body based on Content-Type.
    - Supports form-encoded 'queries' (OpenRefine style).
    - Supports raw JSON body.
    Returns: dict payload
    Raises: ValueError with a message if parsing fails.
    """
    if request.content_type.startswith("application/x-www-form-urlencoded"):
        if not expect_queries:
            raise ValueError("Form-encoded payload only supported with 'queries'")
        queries_param = request.POST.get("queries")
        if not queries_param:
            raise ValueError("Missing 'queries' parameter")
        try:
            return {"queries": json.loads(queries_param)}
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in 'queries' parameter")

    elif request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")

    else:
        raise ValueError(f"Unsupported Content-Type: {request.content_type}")


def process_queries(queries, batch_size=50):
    """
    Enforce batch limit, normalise each query, and return a dict of results.
    """
    messages = []

    if len(queries) > batch_size:
        # Slice rather than reject
        queries = dict(list(queries.items())[:batch_size])
        messages.append(f"Batch size limit exceeded; processing first {batch_size} queries.")

    results = {}
    for key, params in queries.items():
        try:
            query = normalise_query_params(params)
            results[key] = reconcile_place_es(query)
        except ValueError as e:
            results[key] = {"error": str(e), "result": []}
    return {**results, "messages": messages} if messages else results


def normalise_query_params(params):
    """
    Validate and normalise a single reconcile query dict.
    Ensures geometry filters, nearby circle, and query_text are handled consistently.
    Returns a dict with clean values ready for downstream use.
    """
    query_text = params.get("query", "").strip() or None
    size = int(params.get("size", 100))

    # Bounds (GeoJSON-style polygon)
    bounds = None
    if "bounds" in params:
        try:
            geom = params["bounds"].get("geometries", [])[0]
            if geom["type"] != "Polygon":
                raise ValueError("Bounds geometry must be a Polygon")
            bounds = {"type": "Polygon", "coordinates": geom["coordinates"]}
        except Exception as e:
            raise ValueError(f"Invalid bounds: {e}")

    # Nearby (circle)
    lat = lng = radius = None
    has_nearby = False
    if all(k in params for k in ("lat", "lng", "radius")):
        try:
            lat = float(params["lat"])
            lng = float(params["lng"])
            radius = float(params["radius"])
            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90 degrees.")
            if not (-180 <= lng <= 180):
                raise ValueError("Longitude must be between -180 and 180 degrees.")
            if radius <= 0:
                raise ValueError("Radius must be positive.")
            if radius > MAX_EARTH_RADIUS_KM:
                raise ValueError(f"Radius exceeds maximum allowed distance of {MAX_EARTH_RADIUS_KM:.0f} km.")
            has_nearby = True
        except (ValueError, TypeError):
            raise ValueError("Parameters 'lat', 'lng', 'radius' must be numeric.")

    if has_nearby:
        bounds = circle_to_polygon(lat, lng, radius)

    has_dataset = "dataset" in params

    if not query_text and not (bounds or has_nearby or has_dataset):
        raise ValueError("Empty query requires bounds, nearby circle, or dataset filter.")

    fclasses = None
    if "fclasses" in params:
        fclasses = [x.strip().upper() for x in params["fclasses"] if x.strip()]
        invalid = [x for x in fclasses if x not in VALID_FCODES]
        if invalid:
            raise ValueError(
                f"Invalid feature class(es): {', '.join(invalid)}. "
                f"Allowed values are: {', '.join(sorted(VALID_FCODES))}. "
                f"See https://www.geonames.org/source-code/javadoc/org/geonames/FeatureClass.html"
            )

    return {
        "query_text": query_text,
        "size": size,
        "bounds": bounds,
        "lat": lat,
        "lng": lng,
        "radius": radius,
        "has_nearby": bool(has_nearby),
        "has_dataset": bool(has_dataset),
        "fclasses": fclasses,
        "raw": params,  # keep original for additional filters
    }


def es_search_by_ids(ids, index="whg,pub"):
    if not ids:
        return []
    return es_search(index=index, ids=ids)


def reconcile_place_es(query, index="whg,pub"):
    """
    Execute a reconciliation query against Elasticsearch.

    query: dict from normalise_query_params
    """
    hits = es_search(query=query, index=index)
    if not hits:
        return {"result": [], "geojson": None}

    max_score = hits[0]["_score"]
    results = []

    for hit in hits:
        candidate = make_candidate(hit, query["query_text"], max_score)
        results.append(candidate)

    return {
        "result": results
    }


def circle_to_polygon(lat, lng, radius_km, n_points=32):
    """
    Generate a GeoJSON-like polygon approximating a circle, with edges tangent.
    """
    # Expand radius so polygon edges are tangent
    adjusted_radius = radius_km / math.cos(math.pi / n_points)
    coords = []

    for i in range(n_points):
        bearing = (360 / n_points) * i
        dest = geodesic(kilometers=adjusted_radius).destination((lat, lng), bearing)
        coords.append([dest.longitude, dest.latitude])

    # Close the polygon
    coords.append(coords[0])

    return {
        "type": "Polygon",
        "coordinates": [coords]
    }
