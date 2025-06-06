#
# API for external app integrations
# (Sep 2022)
#
import codecs
import datasets.utils
from api.views import collector, responseItem, BadRequestException
from api.serializers import (ErrorResponseSerializer)
from areas.models import Area
from collection.models import Collection
from datasets.models import Dataset, DatasetFile
from datasets.tasks import get_bounds_filter
from places.models import Type
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import View

from rest_framework import (
    viewsets,
    mixins,
    status,
    pagination,
    renderers,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from remote.serializers import *

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample

class NoPagination(pagination.BasePagination):
    def paginate_queryset(self, queryset, request, view=None):
        return None
    def get_paginated_response(self, data):
        return Response(data)

@extend_schema_view(
    list=extend_schema(
        description='Retrieve datasets for authenticated user.',
        parameters=None,
        responses = {
            200: DatasetRemoteSerializer,
            }
        ),
    create=extend_schema(
        description='Create a new dataset for authenticated user.',
        request=DatasetRemoteDetailSerializer,
        parameters=[],
        responses = {
            201: DatasetRemoteDetailSerializer,
            400: ErrorResponseSerializer,
            }
        )
)
class DatasetViewSet(viewsets.ModelViewSet):
    serializer_class = DatasetRemoteDetailSerializer
    queryset = Dataset.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    renderer_classes = [renderers.JSONRenderer] # Prevent inclusion of DatatablesRenderer, set in REST_FRAMEWORK.DEFAULT_RENDERER_CLASSES
    
    def get_pagination_class(self):
        return None

    def get_queryset(self):
        """
        Retrieve datasets for authenticated user.

        Filters datasets based on the authenticated user
        and returns the queryset ordered by ID in descending
        order.
        """
        queryset = self.queryset
        result = queryset.filter(
            # user=self.request.user
            owner=self.request.user
        ).order_by('-id').distinct()
        return result

    def get_serializer_class(self):
        """ Return the serializer class for the request. """
        if self.action == 'list':
            return DatasetRemoteSerializer

        return self.serializer_class
    
    def perform_create(self, serializer):
        """
        Create a new dataset.

        Creates a new dataset for the authenticated user,
        assigns a label if not provided, saves the dataset,
        and creates a new dummy file associated with it.
        """
        try:
            user = self.request.user
            if 'label' not in serializer.validated_data:
                label_out = 'ds_'+ str(Dataset.objects.last().id+1)
            else:
                label_out = serializer.validated_data['label']
            serializer.save(owner=user, label=label_out)
            dsid = Dataset.objects.last()
            filename = 'user_'+str(user.id)+'/'+str(dsid)+'-dummy.txt'
            filepath = 'media/'+filename
            with codecs.open(filepath, mode='w', encoding='utf8') as dummyfile:
                dummyfile.write("# nothing to see here, it's a dummy file")
            DatasetFile.objects.create(
                dataset_id=dsid,
                file=filename,
                format='delimited',
                df_status='dummy',
                upload_date=None,
            )
        except Exception as e:
            raise BadRequestException(detail=str(e))

@extend_schema_view(
    list=extend_schema(
        description='Retrieve places for authenticated user.',
        parameters=None,
        responses = {
            200: PlaceRemoteSerializer,
            }
        ),
    create=extend_schema(
        description='Create a new place for authenticated user.',
        request=PlaceRemoteDetailSerializer,
        parameters=None,
        responses = {
            201: DatasetRemoteDetailSerializer,
            400: ErrorResponseSerializer,
            }
        )
)
class PlaceViewSet(viewsets.ModelViewSet):
    serializer_class = PlaceRemoteDetailSerializer
    queryset = Place.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    renderer_classes = [renderers.JSONRenderer] # Prevent inclusion of DatatablesRenderer, set in REST_FRAMEWORK.DEFAULT_RENDERER_CLASSES
    
    def get_pagination_class(self):
        return None

    def _params_to_ints(self, qs):
        """Convert a list of strings to integers."""
        return [int(str_id) for str_id in qs.split(',')]

    def get_queryset(self):
        """
        Retrieve places for authenticated user.

        Filters places based on the authenticated user and
        returns the queryset ordered by ID in descending
        order.
        """
        links = self.request.query_params.get('links')
        queryset = self.queryset
        if links:
            link_ids = self._params_to_ints(links)
            queryset = queryset.filter(links__id__in=link_ids)

        return queryset.filter(
            user=self.request.user
        ).order_by('-id').distinct()

    def get_serializer_class(self):
        """
        Return the serializer class for the request.

        If the action is for listing, returns a basic serializer
        class, otherwise returns the detailed one.
        """
        """NB we never list places"""
        if self.action == 'list':
            return PlaceRemoteSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        """Create a new place..."""
        try:
            vdata = serializer.validated_data
            ds = vdata['dataset']
            dslabel = ds.label
            if ds.places.count() > 0:
                last_srcid = ds.places.order_by('-id').first().src_id
                last_is_remote = last_srcid.startswith(dslabel)
                if last_is_remote:
                    srcid = dslabel+'_'+str(int(last_srcid[len(dslabel)+1:])+1)
                else:
                    srcid=dslabel+'_1000'
            else:
                srcid=dslabel+'_1000'
    
            cc_in = vdata['ccodes']
            if 'geoms' in vdata:
                geoms = vdata['geoms']
            else:
                geoms = []
            minmax = vdata['minmax']
            if len(cc_in) == 0 and len(geoms) > 0:
                cc_out = datasets.utils.ccodesFromGeom(geoms[0]['jsonb'])
            else:
                cc_out = cc_in
            serializer.save(ccodes=cc_out, src_id=srcid, minmax=minmax)
        except Exception as e:
            raise BadRequestException(detail=str(e))


@extend_schema_view(
    list=extend_schema(
        description='Retrieve collections for authenticated user.',
        parameters=None,
        responses = {
            200: CollectionRemoteSerializer,
            }
        ),
    create=extend_schema(
        description='Create a new collection for authenticated user.',
        request=DatasetRemoteDetailSerializer,
        parameters=[],
        responses = {
            201: CollectionRemoteSerializer,
            400: ErrorResponseSerializer,
            }
        )
)
class CollectionViewSet(viewsets.ModelViewSet):
    """
    Retrieves collections for authenticated user and
    creates a new collection.
    """
    serializer_class = CollectionRemoteSerializer
    queryset = Collection.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    renderer_classes = [renderers.JSONRenderer] # Prevent inclusion of DatatablesRenderer, set in REST_FRAMEWORK.DEFAULT_RENDERER_CLASSES
    
    def get_pagination_class(self):
        return None

    def get_queryset(self):
        """
        Retrieve collections for authenticated user.

        Filters collections based on the authenticated user
        and returns the queryset ordered by ID in descending
        order.
        """
        queryset = self.queryset
        return queryset.filter(
            owner=self.request.user
        ).order_by('-id').distinct()
        
    def perform_create(self, serializer):
        """Create a new collection."""
        try:
            serializer.save(owner=self.request.user)
        except Exception as e:
            raise BadRequestException(detail=str(e))


class TypeViewSet(viewsets.ModelViewSet):
    """
    NOT CURRENTLY IMPLEMENTED
    """
    serializer_class = TypeRemoteSerializerSlim
    queryset = Type.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    renderer_classes = [renderers.JSONRenderer] # Prevent inclusion of DatatablesRenderer, set in REST_FRAMEWORK.DEFAULT_RENDERER_CLASSES
    
    def get_pagination_class(self):
        return None

    # def get_queryset(self):
    #   """Retrieve collections for authenticated user."""
    #   queryset = self.queryset
    #   return queryset.filter(
    #     owner=self.request.user
    #   ).order_by('-id').distinct()
