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
import urllib

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, extend_schema_view
from geopy.distance import geodesic
from rest_framework.views import APIView

from main.choices import FEATURE_CLASSES
from places.models import Place
from .models import APIToken, UserAPIProfile
from .reconcile_helpers import make_candidate, format_extend_row, es_search, ReconcileQuerySerializer

logger = logging.getLogger('reconciliation')

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"
TILESERVER_URL = os.environ.get('TILEBOSS', 'https://tiles.whgazetteer.org').rstrip('/')
MAX_EARTH_RADIUS_KM = math.pi * 6371  # ~20015 km
VALID_FCODES = {fc for fc, _ in FEATURE_CLASSES}
SCHEMA_SPACE = DOMAIN + "/static/whg_place_schema.jsonld"

SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "World Historical Gazetteer Place Reconciliation Service",
    "identifierSpace": DOMAIN + "/place/",
    "schemaSpace": SCHEMA_SPACE,
    "defaultTypes": [
        {
            "id": SCHEMA_SPACE + "#Place",
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
        "url": DOMAIN + "/preview?token={{token}}&id={{id}}",
        "width": 400,
        "height": 300,
    },
    "suggest": {
        "entity": {
            "service_url": DOMAIN,
            "service_path": "/suggest/entity?token={{token}}",
        },
        "property": {
            "service_url": DOMAIN,
            "service_path": "/suggest/property?token={{token}}",
        }
    },
    "extend": {
        "propose_properties": {
            "service_url": DOMAIN,
            "service_path": "/reconcile/properties"
        },
        "property_settings": [
            {
                "name": "limit",
                "label": "Limit",
                "type": "number",
                "default": 0,
                "help_text": "Maximum number of values to return per row (0 for no limit)"
            },
            {
                "name": "content",
                "label": "Content",
                "type": "select",
                "default": "literal",
                "help_text": "Content type: ID or literal",
                "choices": [
                    {
                        "value": "id",
                        "name": "ID"
                    },
                    {
                        "value": "literal",
                        "name": "Literal"
                    }
                ]
            }
        ]
    },
    "batch_size": 50,
    "authentication": {
        "type": "apiKey",
        "name": "token",
        "in": "query",
    }
}

PROPOSE_PROPERTIES = [
    {"id": "whg:geometry", "name": "Geometry (GeoJSON)",
     "description": "The geometrical location (GeoJSON) of the place", "type": "string"},
    {"id": "whg:alt_names", "name": "Alternative names", "description": "Alternative names or aliases for the place",
     "type": "string"},
    {"id": "whg:temporalRange", "name": "Temporal range (years)",
     "description": "The temporal range(s) associated with the place record", "type": "string"},
    {"id": "whg:dataset", "name": "Source dataset",
     "description": "The source dataset from which the place record originates", "type": "string"},
    {"id": "whg:ccodes", "name": "Country codes",
     "description": "The ISO 2-letter country codes associated with the place", "type": "string"},
    {"id": "whg:fclasses", "name": "Feature classes",
     "description": "The feature classes (e.g., 'A' for administrative regions, 'P' for populated places)",
     "type": "string"},
    {"id": "whg:types", "name": "Types", "description": "The types or categories associated with the place",
     "type": "string"},
]


def json_error(message, status=400):
    return JsonResponse({"error": f"{message} See documentation: {DOCS_URL}"}, status=status)


# TODO: Consider using this function to replace part of the current bot-blocking middleware at main.block_user_agents.BlockUserAgentsMiddleware
def authenticate_request(request):
    """
    Authenticate either via:
    1. Authorization: Bearer <token>
    3. token from URL query param
    4. CSRF/session (browser-originated)
    """
    key = None

    # 1. Check Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth.split(" ", 1)[1]

    # 2. Check token from URL query param
    if not key:
        key = request.GET.get("token")

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
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Retrieve Reconciliation Service metadata",
        description=(
            "Returns service metadata, including URLs, default types, and preview configuration. "
            "Supports optional token injection via query parameter."
        ),
        parameters=[
            OpenApiParameter(
                name="token",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="API token to inject into preview URLs",
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Service metadata JSON",
                response=OpenApiTypes.OBJECT,
            )
        },
    ),
    post=extend_schema(
        tags=["Reconciliation API"],
        summary="OpenRefine Reconciliation API",
        description=(
            "Implements the [OpenRefine Reconciliation API](https://reconciliation-api.github.io/specs/latest/).\n\n"
            "Supports two request types:\n"
            "- **Reconciliation**: pass a `queries` object with search terms.\n"
            "- **Extend**: pass an `extend` object with place IDs and requested property IDs.\n\n"
            "Authentication is required via API token."
        ),
        parameters=[
            OpenApiParameter(
                name="queries",
                type=OpenApiTypes.STR,
                required=False,
                location=OpenApiParameter.QUERY,
                description="JSON object with reconciliation queries"
            ),
            OpenApiParameter(
                name="extend",
                type=OpenApiTypes.STR,
                required=False,
                location=OpenApiParameter.QUERY,
                description="JSON object with extension request (ids + properties)"
            ),
        ],
        request={
            "application/json": OpenApiExample(
                "Reconciliation example",
                value={
                    "queries": {
                        "q0": {"query": "Edinburgh", "type": "Place"},
                        "q1": {"query": "Leeds"}
                    }
                },
                # serializer=ReconcileQuerySerializer
            )
        },
        # request=ReconcileQuerySerializer,
        # request_examples=[
        #     OpenApiExample(
        #         "Reconciliation example",
        #         value={
        #             "queries": {
        #                 "q0": {"query": "Edinburgh", "type": "Place"},
        #                 "q1": {"query": "Leeds"}
        #             }
        #         }
        #     )
        # ],
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "oneOf": [
                        {"type": "object", "properties": {"q0": {"type": "object"}}},
                        {"type": "object", "properties": {"rows": {"type": "object"}, "meta": {"type": "array"}}},
                    ],
                },
                description="Successful reconciliation (queries) or extension (extend)",
                examples=[
                    OpenApiExample(
                        "Reconciliation response",
                        value={
                            "q0": {
                                "result": [
                                    {"id": "5426666", "name": "Edinburgh", "score": 95, "match": True}
                                ]
                            }
                        },
                    ),
                    OpenApiExample(
                        "Extend response",
                        value={
                            "meta": [
                                {"id": "whg:ccodes", "name": "Country Codes"},
                                {"id": "whg:geometry", "name": "Geometry"},
                                {"id": "whg:temporalRange", "name": "Temporal Range"},
                            ],
                            "rows": {
                                "5426666": {
                                    "id": "5426666",
                                    "name": "Edinburgh",
                                    "properties": {
                                        "whg:ccodes": ["GB"],
                                        "whg:geometry": [
                                            '{ "type": "Point", "coordinates": [ -3.2, 55.95 ] }'
                                        ],
                                        "whg:temporalRange": [],
                                    },
                                }
                            },
                        },
                    ),
                ],
            ),
            401: OpenApiResponse(description="Authentication failed"),
            400: OpenApiResponse(description="Invalid payload"),
        },
    )
)
class ReconciliationView(APIView):
    def get(self, request, *args, **kwargs):

        logger.debug(f"Request URL (GET): {request.build_absolute_uri()}")

        token = request.GET.get("token")

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

        logger.debug(f"Request URL (POST): {request.build_absolute_uri()}")
        logger.debug(f"Request body: {request.body.decode('utf-8') if request.body else 'No body'}")

        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            payload = parse_request_payload(request)
        except ValueError as e:
            return json_error(str(e))

        extend = payload.get("extend", {})
        if extend:
            ids = extend.get("ids", [])
            properties = extend.get("properties", [])
            if not ids:
                return JsonResponse({"rows": {}, "meta": []})

            qs = Place.objects.filter(id__in=ids).prefetch_related("names", "geoms", "links")

            rows = {str(p.id): format_extend_row(p, properties, request=request) for p in qs}

            # Meta block required by OpenRefine
            meta = [
                {"id": prop.get("id") if isinstance(prop, dict) else prop,
                 "name": prop.get("id") if isinstance(prop, dict) else prop}
                for prop in properties
            ]

            return JsonResponse({"meta": meta, "rows": rows})

        queries = payload.get("queries", {})
        if not queries:
            return json_error("Missing 'queries' parameter")

        results = process_queries(queries, batch_size=SERVICE_METADATA.get("batch_size", 50))
        return JsonResponse(results)


@method_decorator(csrf_exempt, name="dispatch")
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Discover extensible properties",
        description="Returns a list of properties that can be extended, as required by the OpenRefine API.",
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "properties": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                description="A list of available properties.",
                examples=[
                    OpenApiExample(
                        "Example properties response",
                        value={
                            "properties": [
                                {"id": "whg:geometry", "name": "Geometry (GeoJSON)", "type": "string"},
                                {"id": "whg:alt_names", "name": "Alternative names", "type": "string"},
                            ]
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="Authentication failed"),
        },
    )
)
class ExtendProposeView(APIView):

    def get(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        return JsonResponse({
            "properties": PROPOSE_PROPERTIES
        })


@method_decorator(csrf_exempt, name="dispatch")
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Suggest entities based on a prefix",
        description="Returns a list of suggested entities that match a given prefix.",
        parameters=[
            OpenApiParameter(
                name="prefix",
                type=OpenApiTypes.STR,
                description="The string to match against entity names.",
                required=True,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                description="The maximum number of suggestions to return.",
                default=10,
            ),
            OpenApiParameter(
                name="cursor",
                type=OpenApiTypes.INT,
                description="The number of suggestions to skip for pagination.",
                default=0,
            ),
            OpenApiParameter(
                name="exact",
                type=OpenApiTypes.BOOL,
                description="Whether to return exact matches only.",
                default=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "score": {"type": "number"},
                                    "match": {"type": "boolean"},
                                },
                            },
                        }
                    },
                },
                description="A list of matching entity suggestions.",
                examples=[
                    OpenApiExample(
                        "Example entity suggestions",
                        value={
                            "result": [
                                {"id": "5426666", "name": "Edinburgh", "score": 95, "match": True},
                                {"id": "5426667", "name": "Edinburg", "score": 85, "match": False},
                            ]
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="Authentication failed"),
        },
    )
)
class SuggestEntityView(APIView):

    def get(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        prefix = request.GET.get("prefix", "").strip()
        exact = request.GET.get("exact", "false").lower() == "true"

        # Implement the cursor
        try:
            cursor = int(request.GET.get("cursor", 0))
        except (ValueError, TypeError):
            return json_error("Invalid 'cursor' parameter. It must be an integer.")

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

        # Apply the cursor to skip the specified number of results
        hits_to_process = hits[cursor:]

        if not hits_to_process:
            return JsonResponse({"result": []})

        max_score = hits[0].get("_score", 1.0)
        candidates = [make_candidate(hit, query["query_text"], max_score, SCHEMA_SPACE) for hit in hits]

        return JsonResponse({"result": candidates})


@method_decorator(csrf_exempt, name="dispatch")
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Suggest properties based on a prefix",
        description="Returns a list of properties that match a given prefix.",
        parameters=[
            OpenApiParameter(
                name="prefix",
                type=OpenApiTypes.STR,
                description="The string to match against property names.",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                description="The maximum number of suggestions to return.",
                default=10,
            ),
            OpenApiParameter(
                name="cursor",
                type=OpenApiTypes.INT,
                description="The number of suggestions to skip for pagination.",
                default=0,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                description="A list of matching property suggestions.",
                examples=[
                    OpenApiExample(
                        "Example property suggestions",
                        value={
                            "result": [
                                {"id": "whg:ccodes", "name": "Country codes"},
                                {"id": "whg:fclasses", "name": "Feature classes"},
                            ]
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="Authentication failed"),
        },
    )
)
class SuggestPropertyView(APIView):

    def get(self, request, *args, **kwargs):
        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return json_error(auth_error.get("error", "Authentication failed"), status=401)

        try:
            query_text = (request.GET.get("prefix") or request.GET.get("query") or "").strip().lower()
            limit = int(request.GET.get("limit", 10))
            # Get cursor value, defaulting to 0 if not provided
            cursor = int(request.GET.get("cursor", 0))
        except (ValueError, TypeError):
            return json_error("Invalid query parameters")

        # Filter the global constant PROPOSE_PROPERTIES
        if query_text:
            matches = [prop for prop in PROPOSE_PROPERTIES if
                       prop['name'].lower().startswith(query_text)
                       # If prop['id'] contains a colon, check the part after the colon
                       or (':' in prop['id'] and prop['id'].split(':', 1)[1].lower().startswith(query_text))
                       # Also check the full id
                       or prop['id'].lower().startswith(query_text)]
        else:
            matches = PROPOSE_PROPERTIES

        # Apply cursor and limit to the list of matches
        start_index = cursor
        end_index = cursor + limit
        paginated_matches = matches[start_index:end_index]

        return JsonResponse({"result": paginated_matches})


@method_decorator(csrf_exempt, name="dispatch")
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Dummy legacy search endpoint",
        description=(
            "A dummy endpoint to prevent 404 errors from OpenRefine's legacy search calls. "
            "It always returns an empty result."
        ),
        responses={
            200: OpenApiResponse(
                description="Empty result set with a message.",
                examples=[
                    OpenApiExample(
                        "Dummy response",
                        value={
                            "result": [],
                            "message": "OpenRefine legacy search call: no results. Use /suggest/entity endpoint instead."
                        },
                    )
                ],
            )
        },
    )
)
class DummyView(APIView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            "result": [],
            "message": "OpenRefine legacy search call: no results. Use /suggest/entity endpoint instead. See documentation: " + DOCS_URL
        })

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


def parse_request_payload(request):
    """
    Parse request body based on Content-Type.
    - Supports form-encoded 'queries' (OpenRefine style) or 'extend' (OpenRefine data extension).
    - Supports raw JSON body.
    Returns: dict payload
    Raises: ValueError with a message if parsing fails.
    """
    content_type = request.content_type or ""

    # Form-encoded (application/x-www-form-urlencoded)
    if content_type.startswith("application/x-www-form-urlencoded"):
        if "queries" in request.POST:
            queries_param = request.POST["queries"]
            try:
                return {"queries": json.loads(queries_param)}
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in 'queries' parameter")

        elif "extend" in request.POST:
            extend_raw = request.POST["extend"]
            try:
                extend_json = urllib.parse.unquote_plus(extend_raw)
                return {"extend": json.loads(extend_json)}
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in 'extend' parameter")

        else:
            raise ValueError("Missing 'queries' or 'extend' parameter in form-encoded request")

    # JSON body
    elif content_type.startswith("application/json"):
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")

    else:
        raise ValueError(f"Unsupported Content-Type: {content_type}")


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


def reconcile_place_es(query):
    """
    Execute a reconciliation query against Elasticsearch.

    query: dict from normalise_query_params
    """
    hits = es_search(query=query)
    if not hits:
        return {"result": [], "geojson": None}

    logger.debug("Hits: " + json.dumps(hits))

    max_score = hits[0]["_score"]
    results = []

    for hit in hits:
        candidate = make_candidate(hit, query["query_text"], max_score, SCHEMA_SPACE)
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
