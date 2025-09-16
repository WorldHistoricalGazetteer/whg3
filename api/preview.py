import logging

from django.http import JsonResponse, HttpResponseBadRequest, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from places.models import Place, PlaceGeom

logger = logging.getLogger('reconciliation')


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name="dispatch")
class PreviewView(View):

    def get(self, request):
        place_id = request.GET.get("id")
        logger.debug("Preview GET request id=%s", place_id)

        if not place_id:
            return HttpResponseBadRequest("Missing id parameter")

        try:
            place = Place.objects.get(pk=place_id)
        except Place.DoesNotExist:
            raise Http404(f"Place {place_id} not found")

        # Build record using existing logic
        record = self._build_record(place)

        # Render HTML snippet
        html = f"""
        <div style="font-family:sans-serif; font-size:14px; padding:5px;">
            <strong>{record['title']}</strong><br>
            {'; '.join([n['label'] for n in record['names']])}<br>
            Types: {', '.join([t['label'] for t in record['types']])}<br>
            Timespans: {', '.join([str(t) for t in record['timespans']])}<br>
            Centroid: {self._centroid(place)}<br>
            Dataset: {record['dataset']['title']}
        </div>
        """

        return HttpResponse(html, content_type="text/html")

    def _build_record(self, place):
        # Minimal version of your _build_record for preview purposes
        names = [{"label": n.name} for n in place.names.all()]
        types = [{"label": t.label} for t in place.types.all()]
        return {
            "title": place.title,
            "names": names,
            "types": types,
            "timespans": [t[0] for t in place.timespans] if place.timespans else [],
            "dataset": {
                "title": place.dataset.title if place.dataset else "unknown"
            }
        }

    def _centroid(self, place):
        geom = PlaceGeom.objects.filter(place=place).first()
        if geom and geom.geom:
            return f"{geom.geom.centroid.y:.5f}, {geom.geom.centroid.x:.5f}"
        return "n/a"

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. Use GET with ?id=."
        }, status=405)
