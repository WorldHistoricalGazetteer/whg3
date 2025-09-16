import logging

from django.http import JsonResponse, HttpResponseBadRequest, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from places.models import Place, PlaceGeom
from places.utils import attribListFromSet

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

        record = self._build_record(place)

        # Render HTML snippet
        html = f"""
        <div style="font-family:sans-serif; font-size:14px; padding:5px;">
            <strong>{record['title']}</strong><br>
            <strong>Alternative Names:</strong> {'; '.join([n['label'] for n in record['names']])}<br>
            <strong>Types:</strong> {', '.join([t['label'] for t in record['types']])}<br>
            <strong>Country Codes:</strong> {', '.join([c['label'] for c in record['ccodes']])}<br>
            <strong>Feature Classes:</strong> {', '.join([f['label'] for f in record['fclasses']])}<br>
            <strong>Timespans:</strong> {', '.join([str(t) for t in record['timespans']])}<br>
            <strong>Dataset:</strong> {record['dataset']['title']}
            <span style="font-size:10px; color:#888;">Map previews are not yet available.</span>
        </div>
        """

        return HttpResponse(html, content_type="text/html")

    def _build_record(self, place):
        names = attribListFromSet('names', place.names.all(), exclude_title=place.title)
        types = attribListFromSet('types', place.types.all())
        return {
            "title": place.title,
            "names": names,
            "ccodes": place.ccodes,
            "fclasses": place.fclasses,
            "types": types,
            "timespans": [t[0] for t in place.timespans] if place.timespans else [],
            "dataset": {
                "title": place.dataset.title if place.dataset else "unknown"
            }
        }

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({
            "error": "Method not allowed. Use GET with ?id=."
        }, status=405)
