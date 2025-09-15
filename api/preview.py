import json, urllib.parse
from django.views import View
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest

class PreviewView(View):
    def get(self, request):
        data = request.GET.get("data")
        if not data:
            return render(request, "preview_map.html", {"geojson": "{}"})
        try:
            geojson = json.loads(data)
        except json.JSONDecodeError:
            geojson = {}
        return render(request, "preview_map.html", {"geojson": json.dumps(geojson)})

    # def post(self, request):
    #     # Accept JSON payload (from Reconciliation API)
    #     try:
    #         payload = json.loads(request.body)
    #         results = payload.get("results", {})
    #     except Exception:
    #         return HttpResponseBadRequest("Invalid JSON payload")
    #
    #     # Combine all geojsons into one FeatureCollection
    #     combined = {"type": "FeatureCollection", "features": []}
    #     for q in results.values():
    #         gj = q.get("geojson")
    #         if gj and "features" in gj:
    #             combined["features"].extend(gj["features"])
    #
    #     # Check Accept header
    #     if request.headers.get("Accept") == "application/json":
    #         return JsonResponse(combined)
    #
    #     # Otherwise redirect to GET with URL-encoded data
    #     data_param = urllib.parse.quote(json.dumps(combined))
    #     preview_url = f"{request.path}?data={data_param}"
    #     return render(request, "preview_redirect.html", {"url": preview_url})
