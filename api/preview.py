import logging

from django.http import JsonResponse, HttpResponseBadRequest, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample, extend_schema_view
from rest_framework.views import APIView

from api.reconcile import authenticate_request
from api.serializers import PlaceSerializer
from places.models import Place

logger = logging.getLogger('reconciliation')


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name="dispatch")
@extend_schema_view(
    get=extend_schema(
        tags=["Reconciliation API"],
        summary="Reconciliation Preview",
        description=(
                "Returns an HTML snippet for embedding in OpenRefine’s preview pane.\n\n"
                "You must provide a valid `id` parameter (Place ID). "
                "Requires a valid API token via `?token=...`."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                required=True,
                type=int,
                location=OpenApiParameter.QUERY,
                description="Place ID to preview",
            ),
            OpenApiParameter(
                name="token",
                required=True,
                type=str,
                location=OpenApiParameter.QUERY,
                description="API token for authentication",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.STR,
                description="Successful HTML preview snippet",
                examples=[
                    OpenApiExample(
                        "Preview HTML",
                        value=(
                                "<!DOCTYPE html><html><body>"
                                "<div class='record-container'>"
                                "<div class='record-title'>Edinburgh "
                                "<span class='record-note'>Map previews are not yet available.</span>"
                                "</div>"
                                "</div></body></html>"
                        ),
                        media_type="text/html",
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Missing id parameter",
                examples=[
                    OpenApiExample(
                        "Missing ID",
                        value={"error": "Missing id parameter"},
                        response_only=True,
                    )
                ],
            ),
            403: OpenApiResponse(
                description="Invalid API token",
                examples=[
                    OpenApiExample(
                        "Invalid token",
                        value={"error": "Invalid API token"},
                        response_only=True,
                    )
                ],
            ),
            404: OpenApiResponse(
                description="Place not found",
                examples=[
                    OpenApiExample(
                        "Not found",
                        value={"error": "Place 5426666 not found"},
                        response_only=True,
                    )
                ],
            ),
        },
    )
)
class PreviewView(APIView):

    def get(self, request, *args, **kwargs):
        place_id = request.GET.get("id")

        if not place_id:
            return HttpResponseBadRequest("Missing id parameter")

        allowed, auth_error = authenticate_request(request)
        if not allowed:
            return HttpResponse("Invalid API token", status=403)

        try:
            place = Place.objects.get(pk=place_id)
        except Place.DoesNotExist:
            raise Http404(f"Place {place_id} not found")

        serializer = PlaceSerializer(place, context={"request": request})
        record = serializer.data

        def _format_list(data_list, separator=', '):
            if not data_list:
                return "N/A"
            formatted = []
            for item in data_list:
                if isinstance(item, dict):
                    # try 'label' first, then 'name', fallback to str(item)
                    formatted.append(item.get('label') or item.get('name') or str(item))
                else:
                    formatted.append(str(item))
            return separator.join(formatted)

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
                    <span class="record-field">Dataset:</span> {record['dataset']}
                </div>                
            </div>
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html; charset=UTF-8")
