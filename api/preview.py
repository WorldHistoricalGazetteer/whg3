import json
import logging

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from api.reconcile import DOCS_URL
from places.models import Place

logger = logging.getLogger('reconciliation')


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name="dispatch")
class PreviewView(View):

    def get(self, request):
        place_id = request.GET.get("id")
        logger.debug("Preview GET request id=%s", place_id)

        if not place_id:
            return HttpResponseBadRequest("Missing id parameter")

        # Look up Place
        try:
            place = Place.objects.get(pk=place_id)
        except Place.DoesNotExist:
            return HttpResponseBadRequest(f"No Place found with id={place_id}")

        # Build GeoJSON FeatureCollection from related PlaceGeom objects
        features = []
        for geom in place.geoms.all():
            if geom.geom:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(geom.geom.geojson),
                    "properties": {
                        "src_id": geom.src_id,
                        "geom_src": geom.geom_src.src_id if geom.geom_src else None,
                        "task_id": geom.task_id,
                    },
                })
            elif geom.jsonb:
                features.append({
                    "type": "Feature",
                    "geometry": geom.jsonb.get("geometry"),
                    "properties": geom.jsonb.get("properties", {}),
                })

        feature_collection = {
            "type": "FeatureCollection",
            "features": features,
        }

        # If JSON explicitly requested
        if request.headers.get("Accept") == "application/json":
            return JsonResponse(feature_collection)

        # Otherwise, render into Leaflet map
        return render(request, "preview_map.html", {
            "geojson": json.dumps(feature_collection),
            "place": place,  # TODO: Note yet used in template
        })

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. Use GET with ?id=."
        }, status=405)
