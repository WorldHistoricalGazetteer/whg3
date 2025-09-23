# api/views_generic.py

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from api.authentication import AuthenticatedAPIView
from api.querysets import place_preview_queryset, place_feature_queryset, area_owner_queryset, \
    dataset_owner_or_public_queryset, collection_owner_or_public_queryset
from api.schemas import generic_schema
from api.serializers_api import PlaceFeatureSerializer, PlacePreviewSerializer, DatasetFeatureSerializer, \
    DatasetPreviewSerializer, CollectionFeatureSerializer, CollectionPreviewSerializer, AreaFeatureSerializer, \
    AreaPreviewSerializer
from areas.models import Area
from collection.models import Collection
from datasets.models import Dataset
from places.models import Place
from places.views import PlacePortalView

TYPE_MAP = {
    "area": {
        "model": Area,
        "feature_serializer": AreaFeatureSerializer,
        "feature_queryset": area_owner_queryset,
        "preview_serializer": AreaPreviewSerializer,
        "preview_queryset": area_owner_queryset,
    },
    "collection": {
        "model": Collection,
        "feature_serializer": CollectionFeatureSerializer,
        "feature_queryset": collection_owner_or_public_queryset,
        "preview_serializer": CollectionPreviewSerializer,
        "preview_queryset": collection_owner_or_public_queryset,
    },
    "dataset": {
        "model": Dataset,
        "feature_serializer": DatasetFeatureSerializer,
        "feature_queryset": dataset_owner_or_public_queryset,
        "preview_serializer": DatasetPreviewSerializer,
        "preview_queryset": dataset_owner_or_public_queryset,
    },
    "place": {
        "model": Place,
        "detail_view": PlacePortalView,
        "feature_serializer": PlaceFeatureSerializer,
        "feature_queryset": place_feature_queryset,
        "preview_serializer": PlacePreviewSerializer,
        "preview_queryset": place_preview_queryset,
    },
}


@extend_schema(tags=["Schema"])
class CustomSwaggerUIView(TemplateView):
    template_name = "swagger_ui.html"


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('detail')
class GenericDetailView(AuthenticatedAPIView):
    """
    Human-readable detail page for any object type.
    """

    def get(self, request, obj_type, id, *args, **kwargs):
        config = TYPE_MAP.get(obj_type)
        if not config:
            raise Http404(f"Unsupported object type: {obj_type}")

        detail_view = config.get("detail_view")
        if detail_view:
            return detail_view.as_view()(request, pk=id, *args, **kwargs)

        raise Http404(f"No detail view defined for object type '{obj_type}'. Please define one in TYPE_MAP.")


@method_decorator(csrf_exempt, name='dispatch')
@generic_schema('feature')
class GenericFeatureView(AuthenticatedAPIView):
    """
    Returns a machine-readable feature representation (e.g. GeoJSON).
    """

    def get(self, request, obj_type, id, *args, **kwargs):
        config = TYPE_MAP.get(obj_type)
        if not config:
            raise Http404(f"Unsupported object type: {obj_type}")

        queryset_fn = config.get("feature_queryset", lambda user: config["model"].objects)
        qs = queryset_fn(request.user)
        obj = get_object_or_404(qs, pk=id)

        serializer_class = config["feature_serializer"]
        serializer = serializer_class(obj, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name="dispatch")
@generic_schema('preview')
class GenericPreviewView(AuthenticatedAPIView):
    """
    Returns a preview snippet for reconciliation API or human browsing.
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
