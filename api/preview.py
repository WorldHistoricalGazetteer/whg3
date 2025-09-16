import json
import logging

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.reconcile import DOCS_URL

logger = logging.getLogger('reconciliation')


@method_decorator(csrf_exempt, name='dispatch')
class PreviewView(View):

    def post(self, request):
        # Accept JSON payload (e.g., from Reconciliation API)
        try:
            payload = json.loads(request.body)
            results = payload.get("results", {})
        except Exception:
            return HttpResponseBadRequest("Invalid JSON payload")

        # Combine all geojsons into a single FeatureCollection
        combined = {"type": "FeatureCollection", "features": []}
        for q in results.values():
            gj = q.get("geojson")
            if gj and "features" in gj:
                combined["features"].extend(gj["features"])

        # If client explicitly wants JSON, return JSON
        if request.headers.get("Accept") == "application/json":
            return JsonResponse(combined)

        # Otherwise render the HTML template directly with combined GeoJSON
        return render(request, "preview_map.html", {"geojson": json.dumps(combined)})

    ## GET method is not currently used, but could be enabled if needed for testing in a browser.
    ## It would accept a "data" query parameter containing GeoJSON to display.
    def get(self, request):
        logger.debug("Preview GET request params: %s", request.GET)

        data = request.GET.get("data")
        if not data:
            return render(request, "preview_map.html", {"geojson": "{}"})
        try:
            geojson = json.loads(data)
        except json.JSONDecodeError:
            geojson = {}
        return render(request, "preview_map.html", {"geojson": json.dumps(geojson)})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. This endpoint only accepts POST. See documentation: " + DOCS_URL
        }, status=405)
