# periods/api/reconcile.py


import json
import logging

from django.contrib.postgres.search import TrigramSimilarity
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.authentication import TokenQueryOrBearerAuthentication
from periods.models import Chrononym
from .schemas import get_chrononym_reconcile_schema, get_chrononym_suggest_schema, get_chrononym_preview_schema

logger = logging.getLogger('reconciliation')

DOMAIN = "https://whgazetteer.org"  # Use your actual domain
SCHEMA_SPACE = f"{DOMAIN}/schema/chrononym"
DOCS_URL = "https://docs.whgazetteer.org/content/400-Technical.html#reconciliation-api"

CHRONONYM_SERVICE_METADATA = {
    "versions": ["0.2"],
    "name": "PeriodO Chrononyms Reconciliation Service",
    "identifierSpace": f"{DOMAIN}/chrononym/",
    "schemaSpace": SCHEMA_SPACE,
    "defaultTypes": [
        {"id": f"{SCHEMA_SPACE}#Chrononym", "name": "Chrononym"},
    ],
    "documentation": DOCS_URL,
    "logo": DOMAIN + "/static/images/whg_logo_80.png",
    "view": {
        "url": f"{DOMAIN}/chrononym/{{{{id}}}}/",
    },
    "preview": {
        "url": f"{DOMAIN}/chrononym/preview/{{{{id}}}}/?token={{{{token}}}}",
        "width": 400,
        "height": 300,
    },
    "suggest": {
        "entity": {
            "service_url": DOMAIN,
            "service_path": "/chrononym/suggest/?token={{token}}",
        }
    },
    "batch_size": 50,
    "authentication": {
        "type": "apiKey",
        "name": "token",
        "in": "query",
    }
}


def json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@get_chrononym_reconcile_schema()
class ChrononymReconciliationView(APIView):
    """Reconciliation service for PeriodO chrononyms"""

    def get(self, request, *args, **kwargs):
        """Return service specification"""
        token = request.GET.get("token")

        metadata = json.loads(json.dumps(CHRONONYM_SERVICE_METADATA))

        if token:
            # Inject token into URLs
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
    @method_decorator(csrf_exempt, name="dispatch")
    def post(self, request, *args, **kwargs):
        """Handle reconciliation queries"""
        try:
            payload = self.parse_request_payload(request)
        except ValueError as e:
            return json_error(str(e))

        queries = payload.get("queries", {})
        if not queries:
            return json_error("Missing 'queries' parameter")

        # Process queries with batch size limit
        batch_size = CHRONONYM_SERVICE_METADATA.get("batch_size", 50)
        if len(queries) > batch_size:
            queries = dict(list(queries.items())[:batch_size])

        results = {}
        for key, params in queries.items():
            results[key] = self.reconcile_chrononym(params)

        return JsonResponse(results)

    def parse_request_payload(self, request):
        """Parse request body - handles both form-encoded and JSON"""
        content_type = request.content_type or ""

        if content_type.startswith("application/x-www-form-urlencoded"):
            if "queries" in request.POST:
                try:
                    return {"queries": json.loads(request.POST["queries"])}
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON in 'queries' parameter")
            else:
                raise ValueError("Missing 'queries' parameter")

        elif content_type.startswith("application/json"):
            try:
                return json.loads(request.body)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON body")

        else:
            raise ValueError(f"Unsupported Content-Type: {content_type}")

    def reconcile_chrononym(self, params):
        """Reconcile a single chrononym query"""
        query_text = params.get("query", "").strip()
        limit = min(int(params.get("limit", 5)), 20)
        type_filter = params.get("type")

        if not query_text:
            return {"result": []}

        # Type filtering - only accept chrononym type
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


@method_decorator(csrf_exempt, name="dispatch")
@get_chrononym_suggest_schema()
class ChrononymSuggestView(APIView):
    """Entity suggestion for chrononym autocomplete"""

    @authentication_classes([TokenQueryOrBearerAuthentication, SessionAuthentication])
    @permission_classes([IsAuthenticated])
    def get(self, request, *args, **kwargs):
        query = request.GET.get('prefix', '').strip()
        limit = min(int(request.GET.get('limit', 10)), 20)

        if len(query) < 2:
            return JsonResponse({"result": []})

        # Fast prefix search with language info
        suggestions = Chrononym.objects.filter(
            label__istartswith=query
        ).order_by('label')[:limit]

        results = []
        for chrononym in suggestions:
            results.append({
                "id": str(chrononym.id),
                "name": chrononym.label,
                "description": f"Language: {chrononym.languageTag}" if chrononym.languageTag else "",
            })

        # Handle JSONP callback if present
        callback = request.GET.get('callback')
        if callback:
            response_data = f"{callback}({json.dumps({'result': results})})"
            return JsonResponse(response_data, safe=False, content_type='application/javascript')

        return JsonResponse({"result": results})


@method_decorator(csrf_exempt, name="dispatch")
@get_chrononym_preview_schema()
class ChrononymPreviewView(APIView):
    """Preview endpoint for chrononym details"""

    def get(self, request, chrononym_id, *args, **kwargs):
        try:
            chrononym = Chrononym.objects.get(id=chrononym_id)
        except Chrononym.DoesNotExist:
            return JsonResponse({"error": "Chrononym not found"}, status=404)

        # Get related periods for context
        related_periods = chrononym.periods.select_related('authority')[:5]

        # Return JSON data suitable for preview
        data = {
            "id": str(chrononym.id),
            "name": chrononym.label,
            "language": chrononym.languageTag,
            "related_periods_count": chrononym.periods.count(),
            "related_periods": [
                {
                    "id": p.id,
                    "label": p.chrononym or "Untitled Period",
                    "authority": p.authority.id if p.authority else None
                }
                for p in related_periods
            ]
        }

        # Simple HTML preview for embedding
        html_preview = f"""
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h3>{chrononym.label}</h3>
            <p><strong>Language:</strong> {chrononym.languageTag or 'Not specified'}</p>
            <p><strong>Related Periods:</strong> {chrononym.periods.count()}</p>
            {('<ul>' + ''.join([f'<li>{p.chrononym or "Untitled"} ({p.authority.id if p.authority else "Unknown"})</li>' for p in related_periods[:3]]) + '</ul>') if related_periods else '<p><em>No related periods</em></p>'}
        </div>
        """

        # Return HTML or JSON based on Accept header
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse(data)
        else:
            from django.http import HttpResponse
            return HttpResponse(html_preview, content_type='text/html')
