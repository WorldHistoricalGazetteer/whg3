import logging

from django.http import JsonResponse, HttpResponseBadRequest, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from places.models import Place
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

        def _format_list(data_list, separator=', '):
            if data_list:
                # Assuming list of dictionaries with 'label' key, handle simple lists gracefully
                if isinstance(data_list[0], dict):
                    return separator.join([item.get('label', 'N/A') for item in data_list])
                else:
                    return separator.join(str(item) for item in data_list)
            return "N/A"

        # Render HTML snippet
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <style>
                .record-container {{
                    font-family: sans-serif;
                    font-size: 14px;
                    padding: 10px;
                    line-height: 1.5;
                    background-color: #f9f9f9;
                    border-left: 3px solid #007BFF;
                    margin-bottom: 10px;
                }}
                .record-title {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #333;
                }}
                .record-field {{
                    font-weight: bold;
                }}
                .record-info {{
                    margin-top: 5px;
                }}
                .record-note {{
                    font-size: 10px;
                    color: #888;
                    display: inline-block;
                }}
            </style>
        </head>
        <body>
            <div class="record-container">
                <div class="record-title">{record['title']} <span class="record-note">Map previews are not yet available.</span></div>
                <div class="record-info">
                    <span class="record-field">Alternative Names:</span> {_format_list(record.get('names', []))}<br>
                    <span class="record-field">Types:</span> {_format_list(record.get('types', []))}<br>
                    <span class="record-field">Country Codes:</span> {_format_list(record.get('ccodes', []))}<br>
                    <span class="record-field">Feature Classes:</span> {_format_list(record.get('fclasses', []))}<br>
                    <span class="record-field">Timespans:</span> {_format_list(record.get('timespans', []))}<br>
                    <span class="record-field">Dataset:</span> {record['dataset']['title']}
                </div>                
            </div>
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html; charset=UTF-8")

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
