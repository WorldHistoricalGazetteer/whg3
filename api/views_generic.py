# api/views_generic.py
import logging
import os
from urllib.parse import quote as urlquote

from django.http import Http404, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from api.authentication import AuthenticatedAPIView
from api.download_lpf import LPFCache, lpf_stream_from_file, lpf_stream_live, redis_client
from api.schemas import generic_schema, TYPE_MAP

logger = logging.getLogger('reconciliation')


@extend_schema(tags=["Schema"])
class CustomSwaggerUIView(TemplateView):
    template_name = "swagger_ui.html"


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('detail')
class GenericDetailView(AuthenticatedAPIView):
    """
    Human-readable detail page for any object type, typically within the main web app.
    /{obj_type}/{id}/
    """

    def get(self, request, obj_type, id, *args, **kwargs):
        config = TYPE_MAP.get(obj_type)
        if not config:
            raise Http404(f"Unsupported object type: {obj_type}")

        # Use the appropriate queryset function, defaulting to all objects
        qs_fn = config.get("detail_queryset") or config.get("preview_queryset") or (
            lambda user: config["model"].objects)
        obj = get_object_or_404(qs_fn(request.user), pk=id)

        # Special case: periods redirect to PeriodO website
        if obj_type == "period":
            return HttpResponseRedirect(f"http://n2t.net/ark:/99152/{obj.id}")

        # special case: collections branch on collection_class
        if obj_type == "collection":
            if obj.collection_class == "dataset":
                url_name = "collection:ds-collection-browse"
            elif obj.collection_class == "place":
                url_name = "collection:place-collection-browse"
            else:
                raise Http404(f"Unknown collection_class '{obj.collection_class}'")
        else:
            url_name = config.get("detail_url")

        if not url_name:
            raise Http404(f"No detail_url defined for {obj_type}")

        url = reverse(url_name, kwargs={"pid" if obj_type == "place" else "id": obj.pk})

        return HttpResponseRedirect(url)


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('feature')
class GenericFeatureView(AuthenticatedAPIView):
    """
    Returns a machine-readable LPF representation (Linked Places Format).
    /{obj_type}/api/{id}/
    """

    def get(self, request, obj_type, id, *args, **kwargs):
        config = TYPE_MAP.get(obj_type)
        if not config:
            raise Http404(f"Unsupported object type: {obj_type}")

        queryset_fn = config.get("feature_queryset", lambda user: config["model"].objects)
        qs = queryset_fn(request.user)
        obj = get_object_or_404(qs, pk=id)

        # Handle non-streaming serializers
        serializer_class = config.get("feature_serializer", None)
        if serializer_class:
            serializer = serializer_class(obj, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        filename = f"whg_{obj_type}_{id}.lpf.geojson"
        cache_path = LPFCache.get_cache_path(obj_type, id)

        # Log all LPFCache properties for debugging
        logger.debug(f"Cache file exists: {os.path.exists(cache_path)}")
        logger.debug(f"Cache file size: {os.path.getsize(cache_path) if os.path.exists(cache_path) else 'N/A'}")
        logger.debug(f"Build lock key: {LPFCache.get_build_lock_key(obj_type, id)}")
        logger.debug(f"Redis lock TTL: {redis_client.ttl(LPFCache.get_build_lock_key(obj_type, id))}")
        logger.debug(f"LPFCache status for {obj_type} id={id}: is_cached={LPFCache.is_cached(obj_type, id)}, "
                     f"is_building={LPFCache.is_building(obj_type, id)}")

        # Strategy: Stream from cache if available, otherwise stream live and build cache
        if LPFCache.is_cached(obj_type, id):
            logger.debug(f"Serving cached LPF for {obj_type} id={id}")
            # Stream from cached file
            response = StreamingHttpResponse(
                lpf_stream_from_file(cache_path),
                content_type="application/geo+json"
            )
        else:
            # Check if another request is already building the cache
            if not LPFCache.is_building(obj_type, id):
                # Try to acquire lock to build cache
                if LPFCache.acquire_build_lock(obj_type, id):
                    logger.debug(f"Acquired build lock for {obj_type} id={id}")
                    # We got the lock - stream live while building cache
                    response = StreamingHttpResponse(
                        lpf_stream_live(obj_type, obj, request, cache_path),
                        content_type="application/geo+json"
                    )
                else:
                    logger.debug(f"Failed to acquire build lock for {obj_type} id={id}")
                    # Someone else got the lock just before us - stream live without caching
                    response = StreamingHttpResponse(
                        lpf_stream_live(obj_type, obj, request),
                        content_type="application/geo+json"
                    )
            else:
                logger.debug(f"Cache is being built for {obj_type} id={id}, streaming live")
                # Cache is being built by another request - stream live without caching
                response = StreamingHttpResponse(
                    lpf_stream_live(obj_type, obj, request),
                    content_type="application/geo+json"
                )

        response['Content-Disposition'] = f'attachment; filename="{urlquote(filename)}"'
        response['Content-Encoding'] = 'gzip'

        # Keep headers for API consumers, but filename is the key for persistence
        response['X-Format'] = 'Linked Places Format (LPF)'
        response['X-Format-Version'] = 'v1.1'
        response['X-Compatible-With'] = 'GeoJSON'

        return response


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name="dispatch")
@generic_schema('preview')
class GenericPreviewView(AuthenticatedAPIView):
    """
    Returns a preview snippet for reconciliation API or human browsing.
    /{obj_type}/preview/{id}/
    """

    def get(self, request, obj_type, id, *args, **kwargs):
        config = TYPE_MAP.get(obj_type)
        if not config:
            return HttpResponse(f"Unsupported object type: {obj_type}", status=404)

        queryset_fn = config.get("preview_queryset", lambda user: config["model"].objects)
        qs = queryset_fn(request.user)
        obj = get_object_or_404(qs, pk=id)

        serializer_class = config["preview_serializer"]
        serializer = serializer_class(obj, context={"request": request})

        html = render_to_string(
            f"preview/{obj_type}.html",
            {"object": serializer.data},
            request=request,
        )
        return HttpResponse(html, content_type="text/html; charset=UTF-8")


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('create')
class GenericCreateView(AuthenticatedAPIView):
    """
    Create a new object.
    """

    def post(self, request, obj_type, *args, **kwargs):
        # TODO: use forms or DRF serializers depending on workflow
        return Response(
            {"message": f"Create not implemented for {obj_type}"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('update')
class GenericUpdateView(AuthenticatedAPIView):
    """
    Replace (overwrite) an object with new data.
    """

    def put(self, request, obj_type, id, *args, **kwargs):
        return Response(
            {"message": f"Replace not implemented for {obj_type} id={id}"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    # optionally, also allow PATCH for partial updates
    def patch(self, request, obj_type, id, *args, **kwargs):
        return Response(
            {"message": f"Partial replace not implemented for {obj_type} id={id}"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('delete')
class GenericDeleteView(AuthenticatedAPIView):
    """
    Delete an object.
    """

    def delete(self, request, obj_type, id, *args, **kwargs):  # <-- change from post to delete
        config = TYPE_MAP.get(obj_type)
        if not config:
            raise Http404(f"Unsupported object type: {obj_type}")

        return Response(
            {"message": f"Delete not implemented for {obj_type} id={id}"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
