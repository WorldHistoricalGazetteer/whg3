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

from django.contrib.postgres.search import TrigramSimilarity
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, extend_schema_view
from geopy.distance import geodesic
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from main.choices import FEATURE_CLASSES
from periods.models import Period, Chrononym
from places.models import Place
from .authentication import AuthenticatedAPIView, TokenQueryOrBearerAuthentication
from .reconcile_helpers import make_candidate, format_extend_row, es_search, get_propose_properties, \
    extract_entity_type, create_type_guessing_dummies
from .schemas import reconcile_schema, propose_properties_schema, suggest_entity_schema, suggest_property_schema

logger = logging.getLogger('reconciliation')

DOMAIN = os.environ.get('URL_FRONT', 'https://whgazetteer.org').rstrip('/')
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"
TILESERVER_URL = os.environ.get('TILEBOSS', 'https://tiles.whgazetteer.org').rstrip('/')
MAX_EARTH_RADIUS_KM = math.pi * 6371  # ~20015 km
VALID_FCODES = {fc for fc, _ in FEATURE_CLASSES}
SCHEMA_FILE = "/static/whg_schema.jsonld"
SCHEMA_SPACE = DOMAIN + SCHEMA_FILE
PROPOSE_PROPERTIES = get_propose_properties(f"validation{SCHEMA_FILE}")

SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "World Historical Gazetteer Reconciliation Service",
    "identifierSpace": DOMAIN + "/",
    "schemaSpace": SCHEMA_SPACE,
    "defaultTypes": [
        {"id": SCHEMA_SPACE + "#Place", "name": "Place"},
        {"id": SCHEMA_SPACE + "#Period", "name": "Period"},
    ],
    "documentation": DOCS_URL,
    "logo": DOMAIN + "/static/images/whg_logo_80.png",
    "view": {  # human-readable page
        "url": DOMAIN + "/entity/{{id}}/",
    },
    "feature_view": {  # machine-readable place representation
        "url": DOMAIN + "/entity/{{id}}/api",
    },
    "preview": {  # HTML preview snippet
        "url": DOMAIN + "/entity/{{id}}/preview?token={{token}}",
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


def json_error(message, status=400):
    return JsonResponse({"error": f"{message} See documentation: {DOCS_URL}"}, status=status)


@method_decorator(csrf_exempt, name="dispatch")
@reconcile_schema()
class ReconciliationView(APIView):
    def get(self, request, *args, **kwargs):

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

    @authentication_classes([TokenQueryOrBearerAuthentication, SessionAuthentication])
    @permission_classes([IsAuthenticated])
    def post(self, request, *args, **kwargs):

        try:
            payload = parse_request_payload(request)
        except ValueError as e:
            return json_error(str(e))

        # Data extension requests
        extend = payload.get("extend", {})
        if extend:
            entity_ids = extend.get("ids", [])
            if not entity_ids:
                return JsonResponse({"rows": {}, "meta": []})

            try:
                entity_type, ids = extract_entity_type(entity_ids)
            except ValueError as e:
                return json_error(str(e))

            properties = extend.get("properties", [])

            if entity_type == "place":
                qs = Place.objects.filter(id__in=ids).prefetch_related("names", "geoms", "links")
            else:  # period
                qs = Period.objects.filter(id__in=ids)  # TODO: add prefetch

            rows = {
                f"{entity_type}:{p.id}": format_extend_row(p, properties, request=request)
                for p in qs
            }

            # Meta block required by OpenRefine
            meta = [
                {"id": prop.get("id") if isinstance(prop, dict) else prop,
                 "name": prop.get("id") if isinstance(prop, dict) else prop}
                for prop in properties
            ]

            return JsonResponse({"meta": meta, "rows": rows})

        # Reconciliation queries
        queries = payload.get("queries", {})
        if queries:
            try:
                entity_type, _ = extract_entity_type(queries, from_queries=True)
            except ValueError as e:
                return json_error(str(e))

            if not entity_type:
                # If it looks like type guessing, return dummies to force all default types
                all_candidates = create_type_guessing_dummies(SERVICE_METADATA)
                first_query_id = next(iter(queries))
                results = {
                    first_query_id: {"result": all_candidates}
                }
                return JsonResponse(results)

            # Period reconciliation
            batch_size = SERVICE_METADATA.get("batch_size", 50)
            if entity_type == "period":
                if len(queries) > batch_size:
                    queries = dict(list(queries.items())[:batch_size])

                results = {}
                for key, params in queries.items():
                    results[key] = self.reconcile_chrononym(params)

                return JsonResponse(results)

            # Place reconciliation
            results = process_queries(queries, batch_size=batch_size)
            return JsonResponse(results)

        return json_error("Missing 'queries' or 'extend' parameter")

    def reconcile_chrononym(self, params):
        """Reconcile a single chrononym query"""
        query_text = params.get("query", "").strip()
        limit = min(int(params.get("limit", 5)), 20)
        type_filter = params.get("type")

        if not query_text:
            return {"result": []}

        if type_filter and "chrononym" not in type_filter.lower():
            return {"result": []}

        # Multi-tier matching strategy
        results = []

        # 1. Exact matches (score: 100)
        exact_matches = Chrononym.objects.filter(label__iexact=query_text)[:limit]
        for chrononym in exact_matches:
            results.append(self.format_result(chrononym, score=100, match=True))

        if len(results) >= limit:
            return {"result": results[:limit]}

        # 2. Prefix matches (score: 70-95)
        remaining = limit - len(results)
        prefix_matches = Chrononym.objects.filter(
            label__istartswith=query_text
        ).exclude(
            label__iexact=query_text
        )[:remaining * 2]

        for chrononym in prefix_matches:
            score = self.calculate_prefix_score(query_text, chrononym.label)
            results.append(self.format_result(chrononym, score=score))

        if len(results) >= limit:
            results = sorted(results, key=lambda x: x['score'], reverse=True)
            return {"result": results[:limit]}

        # 3. Trigram similarity (score: 30-85)
        remaining = limit - len(results)
        existing_ids = [r['id'] for r in results]

        similarity_matches = Chrononym.objects.annotate(
            similarity=TrigramSimilarity('label', query_text)
        ).filter(
            similarity__gt=0.3
        ).exclude(
            id__in=existing_ids
        ).order_by('-similarity')[:remaining]

        for chrononym in similarity_matches:
            similarity_score = getattr(chrononym, 'similarity', 0)
            score = min(int(similarity_score * 85), 85)
            results.append(self.format_result(chrononym, score=score))

        # Sort and return top results
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        return {"result": results[:limit]}

    def calculate_prefix_score(self, query, label):
        """Calculate score for prefix matches"""
        query_len = len(query)
        label_len = len(label)

        if query_len == label_len:
            return 95
        elif query_len > label_len * 0.8:
            return 90
        elif query_len > label_len * 0.5:
            return 80
        else:
            return 70

    def format_result(self, chrononym, score=50, match=False):
        """Format chrononym as reconciliation result"""
        return {
            "id": str(chrononym.id),
            "name": chrononym.label,
            "type": [{
                "id": f"{SCHEMA_SPACE}#Chrononym",
                "name": "Chrononym"
            }],
            "score": score,
            "match": match,
            "description": f"Language: {chrononym.languageTag}" if chrononym.languageTag else "",
        }

    # def reconcile_chrononym(self, params):
    #     """Reconcile a single chrononym query"""
    #     query_text = params.get("query", "").strip()
    #     limit = min(int(params.get("limit", 5)), 20)
    #     type_filter = params.get("type")
    #
    #     if not query_text:
    #         return {"result": []}
    #
    #     if type_filter and "period" not in type_filter.lower():
    #         return {"result": []}
    #
    #     # --- Annotate the first related Period ID ---
    #     # Subquery to find the ID of the first related Period for each Chrononym
    #     first_period_sq = Period.objects.filter(
    #         chrononyms=OuterRef('pk')
    #     ).values('id')[:1]
    #
    #     # Create a base queryset with the annotated period_id
    #     base_qs = Chrononym.objects.annotate(
    #         period_id=Subquery(first_period_sq)
    #     ).filter(period_id__isnull=False) # Exclude chrononyms without a period
    #
    #     # Multi-tier matching strategy
    #     results = []
    #
    #     # 1. Exact matches (score: 100)
    #     exact_matches = base_qs.filter(label__iexact=query_text)[:limit]
    #     for chrononym in exact_matches:
    #         results.append(self.format_result(chrononym, score=100, match=True))
    #
    #     if len(results) >= limit:
    #         return {"result": results[:limit]}
    #
    #     # 2. Prefix matches (score: 70-95)
    #     remaining = limit - len(results)
    #     prefix_matches = base_qs.filter(
    #         label__istartswith=query_text
    #     ).exclude(
    #         label__iexact=query_text
    #     ).exclude(
    #         id__in=[r['id'].split(':')[1] for r in results] # Filter out results already found
    #     )[:remaining * 2]
    #
    #     for chrononym in prefix_matches:
    #         score = self.calculate_prefix_score(query_text, chrononym.label)
    #         results.append(self.format_result(chrononym, score=score))
    #
    #     if len(results) >= limit:
    #         results = sorted(results, key=lambda x: x['score'], reverse=True)
    #         return {"result": results[:limit]}
    #
    #     # 3. Trigram similarity (score: 30-85)
    #     remaining = limit - len(results)
    #     existing_ids = [r['id'].split(':')[1] for r in results] # IDs are now prefixed, need to strip
    #
    #     # Apply annotation to the similarity query as well
    #     similarity_matches = base_qs.annotate(
    #         similarity=TrigramSimilarity('label', query_text)
    #     ).filter(
    #         similarity__gt=0.3
    #     ).exclude(
    #         id__in=existing_ids
    #     ).order_by('-similarity')[:remaining]
    #
    #     for chrononym in similarity_matches:
    #         similarity_score = getattr(chrononym, 'similarity', 0)
    #         score = min(int(similarity_score * 85), 85)
    #         results.append(self.format_result(chrononym, score=score))
    #
    #     # Sort and return top results
    #     results = sorted(results, key=lambda x: x['score'], reverse=True)
    #     return {"result": results[:limit]}
    #
    # def calculate_prefix_score(self, query, label):
    #     """Calculate score for prefix matches"""
    #     query_len = len(query)
    #     label_len = len(label)
    #
    #     if query_len == label_len:
    #         return 95
    #     elif query_len > label_len * 0.8:
    #         return 90
    #     elif query_len > label_len * 0.5:
    #         return 80
    #     else:
    #         return 70
    #
    # def format_result(self, chrononym, score=50, match=False):
    #     """Format chrononym as reconciliation result"""
    #     period_id = getattr(chrononym, 'period_id', None)
    #     if not period_id:
    #         return None
    #     return {
    #         "id": f"period:{str(period_id)}",
    #         "name": chrononym.label,
    #         "type": [{
    #             "id": f"{SCHEMA_SPACE}#Chrononym",
    #             "name": "Chrononym"
    #         }],
    #         "score": score,
    #         "match": match,
    #         "description": f"Language: {chrononym.languageTag}" if chrononym.languageTag else "",
    #     }


@method_decorator(csrf_exempt, name="dispatch")
@propose_properties_schema()
class ExtendProposeView(APIView):

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            "properties": PROPOSE_PROPERTIES
        })


@method_decorator(csrf_exempt, name="dispatch")
@suggest_entity_schema()
class SuggestEntityView(AuthenticatedAPIView):

    def get(self, request, *args, **kwargs):
        prefix = request.GET.get("prefix", "").strip()

        if not prefix:
            return JsonResponse({"result": []})

        # --- 1. Get Parameters ---
        exact = request.GET.get("exact", "false").lower() == "true"

        try:
            limit = int(request.GET.get("limit", 10))
            cursor = int(request.GET.get("cursor", 0))
        except (ValueError, TypeError):
            return json_error("Invalid 'limit' or 'cursor' parameter. They must be integers.")

        # --- 2. Search for Places (Elasticsearch) ---
        raw_params = {"query": prefix, "size": 50} # Search a large size for combining
        query = normalise_query_params(raw_params)
        query["mode"] = "starts" if exact else "fuzzy"

        place_hits = es_search(query=query)

        # Max score is used for normalizing subsequent scores
        max_score = place_hits[0].get("_score", 1.0) if place_hits else 1.0

        place_candidates = []
        for hit in place_hits:
            candidate = make_candidate(hit, query["query_text"], max_score, SCHEMA_SPACE)
            place_candidates.append(candidate)

        # --- 3. Search for Periods (Database - Chrononym) ---
        period_limit = 20 # Limit the database query size

       # Use an iqueryset to allow for case-insensitive startswith
        suggestions = Chrononym.objects.filter(
            label__istartswith=prefix
        ).order_by('label')[:period_limit]

        period_candidates = []
        PERIOD_SCHEMA_ID = SCHEMA_SPACE + "#Period"

        for chrononym in suggestions:
            period_candidates.append({
                "id": f"period:{chrononym.id}",
                "name": chrononym.label,
                "score": 100, # Assign max score for visibility/sorting
                "match": True,
                "description": f"Language: {chrononym.languageTag}" if chrononym.languageTag else "",
                "type": [{"id": PERIOD_SCHEMA_ID, "name": "Period"}]
            })

        # --- 4. Combine and Sort Results ---
        combined_candidates = place_candidates + period_candidates

        # Sort primarily by score (descending), then alphabetically by name (ascending)
        combined_candidates.sort(key=lambda x: (x.get('score', 0), x.get('name', '')), reverse=True)

        # --- 5. Apply Cursor and Limit (Pagination) ---
        start_index = cursor
        end_index = cursor + limit
        final_candidates = combined_candidates[start_index:end_index]

        # --- 6. Handle JSONP (If present) ---
        callback = request.GET.get('callback')
        results = {"result": final_candidates}

        if callback:
            response_data = f"{callback}({json.dumps(results)})"
            return JsonResponse(response_data, safe=False, content_type='application/javascript')

        return JsonResponse(results)


@method_decorator(csrf_exempt, name="dispatch")
@suggest_property_schema()
class SuggestPropertyView(AuthenticatedAPIView):

    def get(self, request, *args, **kwargs):
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
    get=extend_schema(exclude=True),
    post=extend_schema(exclude=True),
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

    bounds = None

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
    else:
        # Bounds (GeoJSON-style polygon)
        if "bounds" in params:
            try:
                geom = params["bounds"].get("geometries", [])[0]
                if geom["type"] != "Polygon":
                    raise ValueError("Bounds geometry must be a Polygon")
                bounds = {"type": "Polygon", "coordinates": geom["coordinates"]}
            except Exception as e:
                raise ValueError(f"Invalid bounds: {e}")

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
