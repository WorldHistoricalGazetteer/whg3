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
from .reconcile_helpers import make_candidate, format_extend_row, es_search, geoms_to_geojson

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"
TILESERVER_URL = os.environ.get('TILEBOSS', 'https://tiles.whgazetteer.org').rstrip('/')
MAX_EARTH_RADIUS_KM = math.pi * 6371  # ~20015 km
VALID_FCODES = {fc for fc, _ in FEATURE_CLASSES}

SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "World Historical Gazetteer Place Reconciliation Service",
    "identifierSpace": f"{DOMAIN}/place/",
    "schemaSpace": f"{DOMAIN}/static/whg_place_schema.jsonld",
    "defaultTypes": [
        {
            "id": f"{DOMAIN}/static/whg_place_schema.jsonld#Place",
            "name": "Place"
        }
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
        "url": f"{DOMAIN}/preview/",
        "width": 400,
        "height": 400,
    },
    "suggest": {
        "entity": {
            "service_url": f"{DOMAIN}",
            "service_path": "/suggest/entity",
        },
        "property": {
            "service_url": f"{DOMAIN}",
            "service_path": "/suggest/property",
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


# TODO: Consider using this function to replace part of the current bot-blocking middleware at main.block_user_agents.BlockUserAgentsMiddleware
def authenticate_request(request):
    """
    Authenticate either via:
    1. Authorization: Bearer <token>
    2. token=<token> query parameter (only if User-Agent starts with 'OpenRefine')
    3. CSRF/session (browser-originated)
    """
    key = None

    # 1. Check Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth.split(" ", 1)[1]

    # 2. Check query parameter (OpenRefine-only)
    if not key:
        ua = request.headers.get("User-Agent", "")
        if ua.startswith("OpenRefine"):
            key = request.GET.get("token")

    if key:
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
    - `dataset` (int): Restrict to a dataset.
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
        token = request.GET.get("token")

        # Shallow copy so you don't mutate the global SERVICE_METADATA
        metadata = SERVICE_METADATA.copy()

        if token:
            # Inject token into the preview + suggest + extend URLs
            def with_token(url):
                separator = "&" if "?" in url else "?"
                return f"{url}{separator}{urlencode({'token': token})}"

            metadata["preview"]["url"] = with_token(metadata["preview"]["url"])
            metadata["view"]["url"] = with_token(metadata["view"]["url"])
            metadata["feature_view"]["url"] = with_token(metadata["feature_view"]["url"])

            if "suggest" in metadata:
                for _, svc in metadata["suggest"].items():
                    svc["service_url"] = with_token(svc["service_url"])

            if "extend" in metadata and "propose_properties" in metadata["extend"]:
                svc = metadata["extend"]["propose_properties"]
                svc["service_url"] = with_token(svc["service_url"])

            # Overwrite authentication block so OpenRefine knows it's query param style
            metadata["authentication"] = {
                "type": "api_token",
                "name": "token",
                "in": "query"
            }

        return JsonResponse(metadata)

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

        results = process_queries(queries, batch_size=SERVICE_METADATA.get("batch_size", 50))
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

        hits = es_search_by_ids(candidate_ids)

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
    """
    Suggest API endpoint for free-text place search.

    **Endpoint:** `POST /suggest/`

    Accepts a single free-text query and returns candidate matches from the Elastic index.

    **POST payload format:**
    ```json
    {
        "query": "London",
        "limit": 10,
        "mode": "fuzzy"
    }
    ```

    **Parameters:**
    | Parameter | Type    | Description |
    |-----------|---------|-------------|
    | `query`   | string  | Free-text search string (required). |
    | `limit`   | integer | Maximum number of results to return (default 10). |
    | `mode`    | string  | Search mode. Options are `"exact"` (multi-match), `"fuzzy"` (default, `"AUTO"` fuzziness, prefix_length=2), `"starts"` (prefix match), or `"in"` (substring/wildcard match). You may also specify a custom fuzzy mode as `"prefix_length|fuzziness"` (e.g., `"2|1"`), where `prefix_length` is the number of initial characters that must match exactly and `fuzziness` is `"AUTO"` or an integer ≤ 2.

    **Behavior:**
    - Performs a search on the fields: `title^3`, `names.toponym`, `searchy`.
    - Returns candidate matches sorted by relevance score.
    - Each candidate includes canonical name, alternative names, match score (0–100), and exact match flag.

    **Response format:**
    ```json
    {
        "result": [
            {
                "id": "whg:123",
                "name": "London",
                "alt": ["Londinium"],
                "score": 100,
                "exact": true
            }
        ]
    }
    ```
    """

    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = json.loads(request.body)
            raw_params = {
                "query": payload.get("query", ""),
                "size": int(payload.get("limit", 10)),
                "mode": payload.get("mode", "fuzzy"),
            }
            query = normalise_query_params(raw_params)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return json_error(f"Invalid JSON payload or parameters: {e}")

        hits = es_search(query=query)
        if not hits:
            return JsonResponse({"result": []})

        max_score = hits[0].get("_score", 1.0)
        candidates = [make_candidate(hit, query["query_text"], max_score) for hit in hits]

        return JsonResponse({"result": candidates})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class SuggestPropertyView(View):
    """
    /suggest/property
    Returns suggested property names for entities.
    """

    def get_allowed_fields(self):
        # Define all fields that can be suggested
        return [
            "title",
            "whg_id",
            "fclasses",
            "ccodes",
            "timespans",
            "geom",
            "dataset",
            "names",
        ]

    def post(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = json.loads(request.body)
            query_text = (payload.get("query") or "").strip().lower()
            limit = int(payload.get("limit", 10))
        except (json.JSONDecodeError, ValueError, TypeError):
            return json_error("Invalid JSON payload or parameters")

        fields = self.get_allowed_fields()
        # Filter fields by query_text if provided
        if query_text:
            matches = [f for f in fields if query_text in f.lower()]
        else:
            matches = fields

        return JsonResponse({"result": matches[:limit]})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)


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
    results, features = [], []

    for hit in hits:
        candidate = make_candidate(hit, query["query_text"], max_score)
        results.append(candidate)

        geojson = geoms_to_geojson(hit["_source"])
        if geojson:
            features.extend(geojson["features"])

    return {
        "result": results,
        "geojson": {"type": "FeatureCollection", "features": features} if features else None
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
