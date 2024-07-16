# api.views

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.models import Group
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Polygon, Point
# from django.contrib.postgres import search
from django.contrib.gis.measure import D
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import Distance, GeometryField
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import JSONField
from django.db.models import Case, When, Min, Max, Q, F, ExpressionWrapper, fields, Subquery, OuterRef, Count, IntegerField
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.generic import View, ListView
from django.core.paginator import PageNotAnInteger, EmptyPage, Paginator
from django.utils.decorators import method_decorator

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample

from rest_framework import filters
from rest_framework import generics
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import status
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.reverse import reverse
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from accounts.permissions import IsOwnerOrReadOnly
from api.serializers import (
  UserSerializer, DatasetSerializer, PlaceSerializer,
  PlaceTableSerializer, PlaceGeomSerializer, PlaceGeoFeatureSerializer, AreaSerializer,
  FeatureSerializer, LPFSerializer, PlaceCompareSerializer, ErrorResponseSerializer)
from areas.models import Area
from collection.models import Collection, CollPlace
from datasets.models import Dataset
from main.models import Log
from datasets.tasks import get_bounds_filter
from places.models import Place, PlaceGeom
from search.views import getGeomCollection
import inspect
import json
import random
import os, requests

class BadRequestException(APIException):
    serializer_class = ErrorResponseSerializer
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Bad request.'

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        self.detail = {"error": detail}

class GalleryView(ListAPIView):
    pagination_class = PageNumberPagination
    pagination_class.page_size = 6

    def get_queryset(self):
        gallery_type = self.kwargs.get('type')
        model = Collection if gallery_type == 'collections' else Dataset

        filter = Q(public=True)
        if hasattr(model, 'core'): # Omit "core" Datasets
            filter &= Q(core=False)

        # ADD COLLECTION CLASS FILTERS
        classes = self.request.query_params.get('classes', '')
        if classes:
            class_list = classes.split(',')
            classfilters = Q(collection_class__in=class_list)
            if 'student' in class_list:
                classfilters |= Q(nominated=True)
            filter &= classfilters
        elif gallery_type == 'collections':
            return model.objects.none()

        # ADD TEXT FILTERS
        search_text = self.request.query_params.get('q', '') # Default to empty string
        if search_text:
            filter &= (
                Q(title__icontains=search_text) |  # include title field search
                Q(description__icontains=search_text) |  # include description field search
                Q(creator__icontains=search_text)  # include creator field search
            )
            if hasattr(model, 'contributors'):  # Check if contributors field exists in the model (Datasets only)
                filter |= Q(contributors__icontains=search_text)  # include contributors field search if it exists
        queryset = model.objects.filter(filter)

        # SPATIAL FILTERS
        country_codes = self.request.query_params.get('countries', '').split(',')
        print(country_codes)
        if country_codes != ['']:
            country_codes = [code.upper() for code in country_codes]
            queryset = queryset.filter(places__ccodes__overlap=country_codes).distinct()

        # SORTING
        sort_by = self.request.query_params.get('sort', 'title') # Default to `title` alphabetical
        if sort_by.endswith('earliest'): # Use `endswith` to accommodate reverse sorting
            queryset = queryset.annotate(earliest=Min('places__minmax__0'))
        elif sort_by.endswith('latest'):
            queryset = queryset.annotate(latest=Max('places__minmax__1'))
        elif sort_by.endswith('numrows') and gallery_type == 'collections':
            queryset = queryset.annotate(numrows=Count(
                    Case(
                        When(
                            places__isnull=False,
                            then=1,
                        ),
                        output_field=IntegerField(),
                    ),
                    distinct=True,
                ) + Count('datasets__places', distinct=True))
        elif sort_by.endswith('modified'):
            queryset = queryset.annotate(
                modified=Subquery(Log.objects.filter(dataset=OuterRef('pk')).order_by('-timestamp').values('timestamp')[:1])
            )

        return queryset.order_by(sort_by)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Paginate the data
        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(queryset, request)
        except PageNotAnInteger:
            page = 1
        except EmptyPage:
            page = paginator.page.paginator.num_pages

        qs_list = [instance.carousel_metadata for instance in page]
        qs_json = json.dumps(qs_list, default=str)

        response_data = {
            'items': json.loads(qs_json),
            'total_items': queryset.count(),
            'current_page': int(request.query_params.get('page', 1)),
            'total_pages': paginator.page.paginator.num_pages,
        }

        return JsonResponse(response_data, safe=False)

class StandardResultsSetPagination(PageNumberPagination):
  page_size = 10
  page_size_query_param = 'page_size'
  max_page_size = 20000

#
# External API
#
#
"""
  /remote/
  search place index (always whg) parent records
  params: name, name_startswith, fclass, ccode, area, dataset, collection, pagesize, fuzzy
"""
class RemoteIndexAPIView(View):
  authentication_classes = [TokenAuthentication]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    # idx = 'whg'
    idx = settings.ES_WHG
    params = request.GET
    # print('RemoteSearchIndexView request params', params)

    name = params.get('name')
    name_startswith = params.get('name_startswith')
    fc = params.get('fclass', None)
    fclasses = [x.upper() for x in fc.split(',')] if fc else None
    cc = params.get('ccode', None)
    ccodes = [x.upper() for x in cc.split(',')] if cc else None
    area = params.get('area', None)
    dataset = params.get('dataset', None)
    collection = params.get('collection', None)
    pagesize = params.get('pagesize', None)
    offset = params.get('offset', None)
    fuzzy = params.get('fuzzy', None)

    print('offset', offset)

    if all(v is None for v in [name, name_startswith]):
      return HttpResponse(
        content='<h3>Query requires either name or name_startswith</h3>')
    else:
      q = {
        "size": pagesize if pagesize else 10,
        "from": offset if offset else 0,
        "query": {"bool": {
          "must": [
            {"exists": {"field": "whg_id"}},
            {"multi_match": {
              "query": name if name else name_startswith,
              "fields": ["title^3", "names.toponym", "searchy"],
            }}],
          "filter": []
        }}
      }
      if fc:
        q['query']['bool']['must'].append({"terms": {"fclasses": fclasses}})
      if dataset:
        q['query']['bool']['must'].append({"match": {"dataset": dataset}})
      if ccodes:
        q['query']['bool']['must'].append({"terms": {"ccodes": ccodes}})
      if area:
        a = get_object_or_404(Area, pk=area)
        bounds = {"id": [str(a.id)], "type": [a.type]}  # nec. b/c some are polygons, some are multipolygons
        # q['query']['bool']["filter"] = get_bounds_filter(bounds, 'whg')
        q['query']['bool']["filter"].append(get_bounds_filter(bounds, settings.ES_WHG))
      if collection:
        c = get_object_or_404(Collection, pk=collection)
        ds_list = [d.label for d in c.datasets.all()]
        q['query']['bool']["filter"].append({"terms": {"dataset": ds_list}})
      if fuzzy and fuzzy.lower() == 'true':
        q['query']['bool']['must'][1]['multi_match']['fuzziness'] = 'AUTO'
        # up the count of results for fuzzy search
        q['size'] = 20 if not pagesize else pagesize
        q['from'] = 20 if not offset else offset

      print('q', q)

      # run query
      # index_set = collector(q, 'whg')
      index_set = collector(q, settings.ES_WHG)
      print('index_set (collector() result)', index_set)

      # format hit items
      items = [collectionItem(i) for i in index_set['items']]
      # items = [collectionItem(s, 'place', None) for s in index_set['items']]

      # result object
      result = {'type': 'FeatureCollection',
                'count': index_set['count'],
                'offset': q['from'],
                'pagesize': q['size'],
                'features': items[:int(pagesize)] if pagesize else items}

    # to client
    return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})


class SpatialAPIView(generics.ListAPIView):
  """
  This endpoint will return a Feature Collection (in Linked Places Format) containing places either within a given bounding
  box or within a given radial distance from a given point.

  A search `type` of either `bbox` or `nearby` is required. A `bbox` requires south-west (`sw`) and north-east (`ne`) coordinates, while
  a `nearby` search requires `lon` and `lat` of the search centre together with a `km` radius (in kilometres).
  """
  renderer_classes = [JSONRenderer]
  serializer_class = LPFSerializer

  # TODO: Add text filtering?
  # filter_backends = [filters.SearchFilter]
  # search_fields = ['@title']

  @extend_schema(
    parameters=[
        OpenApiParameter(
            name="type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Type of spatial search, either 'nearby' or 'bbox'.",
        ),
        OpenApiParameter(
            name="lon",
            type=OpenApiTypes.FLOAT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Nearby search: center-point longitude coordinate, between -180 and 180 degrees.",
        ),
        OpenApiParameter(
            name="lat",
            type=OpenApiTypes.FLOAT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Nearby search: center-point latitude coordinate, between -90 and 90 degrees.",
        ),
        OpenApiParameter(
            name="km",
            type=OpenApiTypes.FLOAT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Nearby search: radius (in km).",
        ),
        OpenApiParameter(
            name="sw",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Bounding box search: southwest corner coordinates (comma-separated lon,lat values).",
            examples=[
                OpenApiExample(
                    name="Example sw",
                    summary="Example of southwest corner coordinates",
                    #description="This is an example of southwest corner coordinates.",
                    value="-150.123456,-52.345678"
                )
            ],
        ),
        OpenApiParameter(
            name="ne",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Bounding box search: northeast corner coordinates (comma-separated lon,lat values).",
            examples=[
                OpenApiExample(
                    name="Example ne",
                    summary="Example of northeast corner coordinates",
                    #description="This is an example of northeast corner coordinates.",
                    value="150.123456,52.345678"
                )
            ],
        ),
        OpenApiParameter(
            name="fc",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Comma-separated list of feature classes to filter by."
        ),
        OpenApiParameter(
            name="dataset",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by dataset ID."
        ),
        OpenApiParameter(
            name="collection",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by collection ID."
        ),
        OpenApiParameter(
            name="pagesize",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Number of results per page."
        ),
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="A page number within a paginated result set."
        ),
    ],
    responses = {
        200: LPFSerializer(many=True),
        400: ErrorResponseSerializer,
    }
  )

  def get(self, *args, **kwargs):
    params = self.request.query_params
    print('SpatialAPIView() params', params)

    qtype = params.get('type', None)
    lon = params.get('lon', None)
    lat = params.get('lat', None)
    dist = params.get('km', None)
    sw = params.get('sw', None)
    ne = params.get('ne', None)
    fc = params.get('fc', None)
    fclasses = list(set([x.upper() for x in ','.join(fc)])) if fc else None
    ds = params.get('dataset', None)
    coll = params.get('collection', None)
    pagesize = params.get('pagesize', None)
    try:
        pagesize = int(pagesize)
    except (TypeError, ValueError):
        pagesize = 20
    # year = params.get('year', None)

    err_note = None

    # Use Place records and LPFSerializer
    if not qtype:
        raise BadRequestException("Spatial query parameters must include either 'type=nearby' or 'type=bbox'.")
    elif qtype == 'nearby':
      # http://localhost:8001/api/spatial/?type=nearby&lon=-103.71&lat=20.66&km=100&dataset=lugares20_redux
      # 33.285556,26.809167
        if not all(v for v in [lon, lat, dist]):
            raise BadRequestException("A 'nearby' spatial query requires 'lon', 'lat', and 'km' parameters.")
        else:
            pnt = Point(float(lon), float(lat), srid=4326)
            qs = Place.objects.filter(dataset__public=True, geoms__jsonb__type='Point')
            placeids = PlaceGeom.objects.filter(geom__distance_lte=(pnt, D(km=float(dist)))).values_list('place_id')
            msg = "nearby query (lon, lat): " + str(pnt.coords) + ' w/' + str(dist) + 'km buffer'
            print(msg)
    elif qtype == 'bbox':
        if not all(v for v in [sw, ne]):
            raise BadRequestException("A 'bbox' spatial query requires both 'sw' and 'ne' parameters.")
        else:
            qs = Place.objects.filter(dataset__public=True, geoms__jsonb__type='Point')
            bb = [float(sw.split(',')[0]), float(sw.split(',')[1]), float(ne.split(',')[0]), float(ne.split(',')[1])]
            bbox = Polygon.from_bbox(bb) # [xmin, ymin, xmax, ymax]
            placeids = PlaceGeom.objects.filter(geom__within=bbox).values_list('place_id')
            msg="bbox query (sw, ne): "+str(bbox)
            print(msg)

    qs = qs.filter(id__in=placeids)
    # filter on params
    if coll:
        collids = Collection.objects.get(id=coll).places.all().values_list('id', flat=True)
        qs = qs.filter(id__in=collids)
    qs = qs.filter(dataset=ds) if ds else qs
    qs = qs.filter(fclasses__overlap=fclasses) if fclasses else qs

    filtered = qs[:pagesize]
    print(filtered)
    serializer = LPFSerializer(filtered, many=True, context={'request': self.request})
    result = {
        "count": qs.count(),
        "pagesize": filtered.count(),
        "parameters": params,
        "errors": err_note,
        "type": "FeatureCollection",
        "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
        "features": serializer.data
    }
    #print('place result',result)
    return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})

"""
  makeGeom(); called by responseItem(), childItem
  format index locations as geojson
"""
def makeGeom(geom):
  #print('geom',geom)
  # TODO: account for non-point
  if len(geom) > 1:
    geomobj = {"type":"GeometryCollection", "geometries": []}
    for g in geom:
      geomobj['geometries'].append(g['location'])
  elif len(geom) == 1:
    geomobj=geom[0]['location']
  else:
    geomobj=None
  return geomobj


def childItem(i):
  _id = i['_id']
  score = i.get('_score', None)
  i = i['_source']
  item = {
    "type": "Feature",
    "score": score,
    "properties": {
        "title": i.get('title', ''),
        "index_id": _id,
        "index_role": i.get('relation', {}).get('name', ''),
        "place_id": i.get('place_id', ''),
        "source_id": i.get('src_id', ''),
        "dataset": i.get('dataset', ''),
    },
    "fclasses": [fc for fc in (i.get('fclasses') or []) if fc is not None],
    "types": [t.get('sourceLabel', t.get('source_label')) for t in (i.get('types') or []) if t is not None],
    "variants": [n['toponym'] for n in (i.get('names') or []) if n.get('toponym') != i.get('title')],
    'links': i.get('links', []),
    "when": [{"start": {"in": ts.get("gte")}, "end": {"in": ts.get("lte")}} for ts in (i.get('timespans') or []) if ts is not None],
    "minmax": [i['minmax'].get('gte'), i['minmax'].get('lte')] if isinstance(i.get('minmax'), dict) else [],
    "ccodes": i.get('ccodes', []),
    "geometry": makeGeom(i.get('geoms', []))
  }
  return item
"""
  responseItem(); called by collector();
  formats api search parent hits
"""
def responseItem(i):
  # print('i in responseItem',i)
  _id = i['_id']
  score = i.get('score', None)
  # serialize as geojson
  i = i['hit']
  # print("i['names']", i['names'])
  item = {
    "type":"Feature",
    "score": score,
    "properties": {
      "title":i['title'],
      "index_id":_id,
      "index_role":i['relation']['name'],
      "place_id":i['place_id'],
      "child_place_ids":[int(c) for c in i['children']],
      "dataset":i['dataset'],
      "fclasses": [c for c in i['fclasses']],
      "placetypes": [t.get('sourceLabel', t.get('source_label')) for t in i['types']],
      # "variants":[n for n in i['suggest']['input'] if n != i['title']],
      "variants":[n['toponym'] for n in i['names'] if n['toponym'] != i['title']],
      'links':i['links'],
      "timespans":i['timespans'],
      "minmax":i['minmax'] if 'minmax' in i.keys() else [],
      "ccodes":i['ccodes']
    },
    "geometry": makeGeom(i['geoms'])
  }
  return item

"""
  collector(); called by IndexAPIView(), RemoteIndexAPIView()
  execute es.search, return results post-processed by suggestionItem()
"""
def collector(q, idx):
  es = settings.ES_CONN
  items = []

  # TODO: trap errors
  res = es.search(index=idx, body=q)
  # print('res', res)
  hits = res['hits']['hits']
  # print('inner hits in collector()', json.dumps([h['inner_hits'] for h in hits], indent=2))
  # [dict_keys(['_index', '_id', '_score', '_source', 'inner_hits'])]
  count = res['hits']['total']['value']
  if len(hits) > 0:
    for h in hits:
      # print('h in collector()', h)
      items.append(
        {"_id": h['_id'],
         "linkcount": len(h['_source']['links']),
         "childcount": len(h['_source']['children']),
         "score": h['_score'],
         "hit": h['_source'],
         "inner_hits": h['inner_hits'] if 'inner_hits' in h.keys() else "no inner hits"
         }
      )
  # print('items', items) # 1 item
  # print('item keys', items[0].keys())
  # print('item inner_hits', items[0]['inner_hits'])
  result = {"count": count,
            "items": sorted(items, key=lambda x: x['score'], reverse=True)}
  return result

"""
  bundler();  called by IndexAPIView, case api/index?whgid=
  execute es.search, return post-processed results
"""
def bundler(q, whgid, idx):
  # idx is ['whg', 'pub']
  es = settings.ES_CONN
  res = es.search(index=idx, body=q)
  hits = res['hits']['hits']
  bundle = []
  if len(hits) > 0:
    for h in hits:
      bundle.append(
        {"_id": h['_id'],
         "linkcount":len(h['_source']['links']),
         "childcount":len(h['_source']['children']),
         "score": h['_score'],
         "hit": h['_source'],
        }
      )
  stuff = [responseItem(i) for i in bundle]
  return stuff

"""
  /api/index?
  search whg & pub indexes
"""


class IndexAPIView(View):
  def get(self, request):
    params = request.GET
    print('IndexAPIView request.GET', params)
    # idx = ['whg', 'pub']  # search both indexes
    idx = [settings.ES_WHG, settings.ES_PUB]  # search both indexes

    name = request.GET.get('name')
    whgid = request.GET.get('whgid')  # a parent record
    pid = request.GET.get('pid')  # place.id > place_id
    fc = params.get('fclass', None)  # feature class
    fclasses = [x.upper() for x in fc.split(',')] if fc else None
    dataset = request.GET.get('dataset')  # dataset label
    cc = request.GET.get('ccode')  # country code
    ccodes = [x.upper() for x in cc.split(',')] if cc else None
    year = request.GET.get('year')
    area = request.GET.get('area')
    pagesize = params.get('pagesize', None)

    if all(v is None for v in [name, whgid, pid]):
      return JsonResponse({
        'error': 'Query requires either name, namestartswith, pid, or whgid',
        'instructions': 'API instructions can be found at https://whgazetteer/usingapi/'
      }, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2}, status=400)

    else:
      if whgid and whgid != '':
        print('fetching whg_id', whgid)
        q = {
          "query": {
            "bool": {
              "should": [
                {"parent_id": {"type": "child", "id": whgid}},
                {"match": {"_id": whgid}}
              ]
            }
          }
        }
        bundle = bundler(q, whgid, idx)
        print('bundler q', q)
        result = {"index_id": whgid,
                  "note": str(len(bundle)) + " records in WHGasserted as skos:closeMatch",
                  "type": "FeatureCollection",
                  "features": [b for b in bundle]}
      else:
        q = {
          "size": 100,
          "query": {
            "bool": {
              "must": [
                {"exists": {"field": "whg_id"}},
                {"multi_match": {
                  "query": name,
                  "fields": ["title^3", "names.toponym", "searchy"]
                }}
              ],
              "should": [
                {
                  "has_child": {
                    "type": "child",
                    "query": {
                      "match_all": {}
                    },
                    "inner_hits": {}
                  }
                }
              ]
            }
          }
        }
        if fc:
          q['query']['bool']['must'].append({"terms": {"fclasses": fclasses}})
        if dataset:
          q['query']['bool']['must'].append({"match": {"dataset": dataset}})
        if ccodes:
          q['query']['bool']['must'].append({"terms": {"ccodes": ccodes}})
        if year:
          q['query']['bool']['must'].append({"term": {"timespans.value": year}})
        if area:
          a = get_object_or_404(Area, pk=area)
          bounds = {"id": [str(a.id)], "type": [a.type]}  # necessary because some are polygons, some are multipolygons
          # q['query']['bool']["filter"] = get_bounds_filter(bounds, 'whg')
          q['query']['bool']["filter"] = get_bounds_filter(bounds, settings.ES_WHG)

        # print('the api query was:', json.dumps(q, indent=2))
        # run query
        # response = collector(q, 'whg')
        response = collector(q, settings.ES_WHG)
        # print('response in IndexAPIView()', response)
        print('len(items)', len(response['items']))
        # ex = response['items'][1]
        union_records = []
        for item in response['items']:
          parent = responseItem(item)
          print()
          # print('formatted parent', parent)
          union_records.append(parent)  # the parent
          # all parents have inner_hits, not all have children
          children = item['inner_hits']['child']['hits']['hits']
          if len(children) > 0:
            for child in children:
              # needs formatting as a Feature
              # print()
              # print('child', childItem(child))
              union_records.append(childItem(child)) # the children
        print(str(len(union_records)) + ' total records returned')
        result = {
          'note': str(len(union_records)) + " records in WHG asserted as skos:closeMatch",
          'type': 'FeatureCollection',
          'pagesize': pagesize,
          'features': union_records[:int(pagesize)] if pagesize else union_records}

    # to client
    return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})


# class IndexAPIView(View):
#   def get(self, request):
#     params = request.GET
#     print('IndexAPIView request.GET', params)
#     idx = ['whg', 'pub']  # search both indexes
#
#     name = request.GET.get('name')
#     whgid = request.GET.get('whgid')  # a parent record
#     pid = request.GET.get('pid')  # place.id > place_id
#     fc = params.get('fclass', None)  # feature class
#     fclasses = [x.upper() for x in fc.split(',')] if fc else None
#     dataset = request.GET.get('dataset')  # dataset label
#     cc = request.GET.get('ccode')  # country code
#     ccodes = [x.upper() for x in cc.split(',')] if cc else None
#     year = request.GET.get('year')
#     area = request.GET.get('area')
#     pagesize = params.get('pagesize', None)
#
#     if all(v is None for v in [name, whgid, pid]):
#       return JsonResponse({
#         'error': 'Query requires either name, namestartswith, pid, or whgid',
#         'instructions': 'API instructions can be found at https://whgazetteer/usingapi/'
#       }, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2}, status=400)
#
#     else:
#       if whgid and whgid != '':
#         print('fetching whg_id', whgid)
#         q = {
#           "query": {
#             "bool": {
#               "should": [
#                 {"parent_id": {"type": "child", "id": whgid}},
#                 {"match": {"_id": whgid}}
#               ]
#             }
#           }
#         }
#         bundle = bundler(q, whgid, idx)
#         print('bundler q', q)
#         result = {"index_id": whgid,
#                   "note": str(len(bundle)) + " records asserted as skos:closeMatch",
#                   "type": "FeatureCollection",
#                   "features": [b for b in bundle]}
#       else:
#         q = {
#           "size": 100,
#           "query": {
#             "bool": {
#               "must": [
#                 {"exists": {"field": "whg_id"}},
#                 {"multi_match": {
#                   "query": name,
#                   "fields": ["title^3", "names.toponym", "searchy"],
#                 }}
#               ]
#             }
#           },
#           "aggs": {
#             "children": {
#               "terms": {"field": "relation.name"},
#               "aggs": {
#                 "child_docs": {
#                   "top_hits": {
#                     "size": 100,
#                     "_source": ["title", "names", "searchy"]
#                   }
#                 }
#               }
#             }
#           }
#         }
#         if fc:
#           q['query']['bool']['must'].append({"terms": {"fclasses": fclasses}})
#         if dataset:
#           q['query']['bool']['must'].append({"match": {"dataset": dataset}})
#         if ccodes:
#           q['query']['bool']['must'].append({"terms": {"ccodes": ccodes}})
#         if year:
#           q['query']['bool']['must'].append({"term": {"timespans.value": year}})
#         if area:
#           a = get_object_or_404(Area, pk=area)
#           bounds = {"id": [str(a.id)], "type": [a.type]}  # nec. b/c some are polygons, some are multipolygons
#           q['query']['bool']["filter"] = get_bounds_filter(bounds, 'whg')
#
#         print('the api query was:', json.dumps(q, indent=2))
#
#         # run query
#         response = collector(q, 'whg')
#         print('response in IndexAPIView()', response)
#
#         union_records = []
#         for parent in response['hits']['hits']:
#           union_record = responseItem(parent)
#           if 'inner_hits' in parent:
#             children = parent['inner_hits']['child']['hits']['hits']
#             for child in children:
#               union_record['features'].append(responseItem(child))
#           union_records.append(union_record)
#
#         # result object
#         result = {'type': 'FeatureCollection',
#                   'count': len(union_records),
#                   'pagesize': pagesize,
#                   'features': union_records[:int(pagesize)] if pagesize else union_records}
#
#     # to client
#     return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})
#

"""

  /api/db?
  SearchAPIView()
  return lpf results from database search
"""
class SearchAPIView(generics.ListAPIView):
  renderer_classes = [JSONRenderer]
  filter_backends = [filters.SearchFilter]
  search_fields = ['@title']

  def get(self, format=None, *args, **kwargs):
    params=self.request.query_params
    print('SearchAPIView() params', params)

    id_ = params.get('id',None)
    name = params.get('name',None)
    name_contains = params.get('name_contains',None)
    cc = map(str.upper, params.get('ccode').split(',')) if params.get('ccode') else None
    ds = params.get('dataset',None)
    fc = params.get('fc',None)
    fclasses=list(set([x.upper() for x in ','.join(fc)])) if fc else None
    year = params.get('year',None)
    pagesize = params.get('pagesize',None)
    err_note = None
    context = params.get('context',None)
    # params
    print({"id_":id_, "fclasses":fclasses})

    qs = Place.objects.filter(Q(dataset__public=True) | Q(dataset__core=True))

    if all(v is None for v in [name,name_contains,id_]):
      # TODO: return a template with API instructions
      return HttpResponse(content=b'<h3>Needs either a "name", a "name_contains", or "id" parameter at \
          minimum <br/>(e.g. ?name=myplacename or ?name_contains=astring or ?id=integer)</h3>')
    else:
      if id_:
        qs=qs.filter(id=id_)
        err_note = 'id given, other parameters ignored' if len(params.keys())>1 else None
        print('qs', qs)
      else:
        qs = qs.filter(minmax__0__lte=year,minmax__1__gte=year) if year else qs
        qs = qs.filter(fclasses__overlap=fclasses) if fc else qs

        if name_contains:
          qs = qs.filter(title__icontains=name_contains)
        elif name and name != '':
          #qs = qs.filter(title__istartswith=name)
          qs = qs.filter(names__jsonb__toponym__icontains=name)

        qs = qs.filter(dataset=ds) if ds else qs
        qs = qs.filter(ccodes__overlap=cc) if cc else qs

      filtered = qs[:pagesize] if pagesize and pagesize < 200 else qs[:20]

      #serial = LPFSerializer if context else SearchDatabaseSerializer
      serial = LPFSerializer
      serializer = serial(filtered, many=True, context={'request': self.request})

      serialized_data = serializer.data
      result = {"count":qs.count(),
                "pagesize": len(filtered),
                "parameters": params,
                "note": err_note,
                "type": "FeatureCollection",
                "features":serialized_data
                }
      #print('place result',result)
      return JsonResponse(result, safe=False,json_dumps_params={'ensure_ascii':False,'indent':2})


""" *** """
""" TODO: the next two attempt the same and are WAY TOO SLOW """
"""
    api/places/<str:dslabel>/[?q={string}]
    Paged list of places in dataset.
"""
class PlaceAPIView(generics.ListAPIView):
  serializer_class = PlaceSerializer
  pagination_class = StandardResultsSetPagination

  def get_queryset(self, format=None, *args, **kwargs):
    print('kwargs',self.kwargs)
    print('self.request.GET',self.request.GET)
    dslabel=self.kwargs['dslabel']
    qs = Place.objects.all().filter(dataset=dslabel).order_by('title')
    query = self.request.GET.get('q')
    if query is not None:
      qs = qs.filter(title__icontains=query)
    return qs

  permission_classes = [permissions.IsAuthenticatedOrReadOnly,IsOwnerOrReadOnly]


"""
    api/dataset/<str:dslabel>/lpf/
    all places in a dataset, for download
"""
class DownloadDatasetAPIView(generics.ListAPIView):
  """  Dataset as LPF FeatureCollection  """
  #serializer_class = PlaceSerializer
  #pagination_class = StandardResultsSetPagination

  def get(self, format=None):
    print('self.request.GET',self.request.GET)
    dslabel=self.request.GET.get('dataset')
    ds=get_object_or_404(Dataset,label=dslabel)
    features = []
    qs = ds.places.all()
    for p in qs:
      rec = {"type":"Feature",
             "properties":{"id":p.id,"src_id":p.src_id,"title":p.title,"ccodes":p.ccodes},
             "geometry":{"type":"GeometryCollection",
                         "features":[g.jsonb for g in p.geoms.all()]},
             "names": [n.jsonb for n in p.names.all()],
             "types": [t.jsonb for t in p.types.all()],
             "links": [l.jsonb for l in p.links.all()],
             "whens": [w.jsonb for w in p.whens.all()],
      }
      #print('rec',rec)
      features.append(rec)

    result={"type":"FeatureCollection", "features": features}
    print('result',result)
    return JsonResponse(result, safe=False,json_dumps_params={'ensure_ascii':False,'indent':2})

  #permission_classes = [permissions.IsAuthenticatedOrReadOnly,IsOwnerOrReadOnly]

"""
  /api/datasets? > query public datasets by id, label, term
"""
# class DatasetAPIView(LoginRequiredMixin, generics.ListAPIView):
#   """    List public datasets    """
#   serializer_class = DatasetSerializer
#   renderer_classes = [JSONRenderer]
#
#   def get_queryset(self, format=None, *args, **kwargs):
#     params=self.request.query_params
#     print('api/datasets params',params)
#     id_ = params.get('id', None)
#     dslabel = params.get('label', None)
#     query = params.get('q', None)
#
#     qs = Dataset.objects.filter(Q(public=True) | Q(core=True)).order_by('label')
#
#     if id_:
#       qs = qs.filter(id = id_)
#     elif dslabel:
#       qs = qs.filter(label = dslabel)
#     elif query:
#       qs = qs.filter(Q(description__icontains=query) | Q(title__icontains=query))
#
#     print('qs',qs)
#     result = {
#               "count":qs.count(),
#               "parameters": params,
#               #"features":serialized_data
#               "features":qs
#               }
#     print('ds result', result,type(result))
#     return qs
from rest_framework.response import Response

class DatasetAPIView(LoginRequiredMixin, generics.ListAPIView):
    """List public datasets"""
    serializer_class = DatasetSerializer
    renderer_classes = [JSONRenderer]

    def list(self, request, *args, **kwargs):
        params = self.request.query_params
        id_ = params.get('id', None)
        dslabel = params.get('label', None)
        query = params.get('q', None)

        qs = Dataset.objects.filter(Q(public=True) | Q(core=True)).order_by('label')

        if id_:
            qs = qs.filter(id=id_)
        elif dslabel:
            qs = qs.filter(label=dslabel)
        elif query:
            qs = qs.filter(Q(description__icontains=query) | Q(title__icontains=query))

        serializer = self.get_serializer(qs, many=True)
        data = {
            "count": qs.count(),
            "parameters": params,
            "features": serializer.data
        }
        return JsonResponse(data, safe=False, json_dumps_params={'indent': 2})

"""
  /api/area_features
"""
# geojson feature for api
class AreaFeaturesView(generics.ListAPIView):
  #@staticmethod

  def get(self, format=None, *args, **kwargs):
    params=self.request.query_params
    user = self.request.user
    print('params', params)
    print('api/areas request',self.request)

    id_ = params.get('id', None)
    query = params.get('q', None)
    filter = params.get('filter', None)
    regions = params.get('regions', None)

    areas = []
    qs = Area.objects.all().filter((Q(type='predefined'))).values('id','title','type','description','geojson')

    # filter for parameters
    if id_:
      qs=qs.filter(id=id_)
    if query:
      qs = qs.filter(title__icontains=query)
    if filter and filter == 'un':
      qs = qs.filter(description="UN Statistical Division Sub-Region")
    if regions is not None:
        qs = qs.filter(id__in=[int(region_id) for region_id in regions.split(',')])

    for a in qs:
      feat = {
        "type":"Feature",
        "properties":{"id":a['id'],"title":a['title'],"type":a['type'],"description":a['description']},
        "geometry":a['geojson']
      }
      areas.append(feat)

    # return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    return JsonResponse(areas, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})

"""
  /api/user_area_features
"""
# geojson feature for api
@method_decorator(login_required, name='dispatch')
class UserAreaFeaturesView(APIView):

    def get(self, request, format=None, *args, **kwargs):
        user = self.request.user
        areas = []

        # Filter areas based on the user
        qs = Area.objects.filter(owner=user, type__in=['ccodes', 'copied', 'drawn']).values('id', 'title', 'type', 'description', 'geojson')

        for a in qs:
            feat = {
                "type": "Feature",
                "properties": {"id": a['id'], "title": a['title'], "type": a['type'], "description": a['description']},
                "geometry": a['geojson']
            }
            areas.append(feat)

        return Response(areas, status=status.HTTP_200_OK)

class UserList(generics.ListAPIView):
  queryset = User.objects.all()
  serializer_class = UserSerializer

class UserDetail(generics.RetrieveAPIView):
  queryset = User.objects.all()
  serializer_class = UserSerializer

"""
  API 'home page' (not implemented)
"""
@api_view(['GET'])
def api_root(request, format=None):
  return Response({
    # 'datasets': reverse('dataset-list', request=request, format=format)
    'datasets': reverse('api:ds-list', request=request, format=format)
  })


class PrettyJsonRenderer(JSONRenderer):
  def get_indent(self, accepted_media_type, renderer_context):
    return 2

#

# IN USE May 2020

#
"""
    place/<int:pk>/ **OR** 'place/<str:pk_list>/'
    uses: ds_browse.html; place_collection_browse.html
    "published record by place_id"
"""
## SUPERSEDED BY PlacesDetailAPIView BELOW
# class PlaceDetailAPIView(generics.RetrieveAPIView):
#   """  returns single serialized database place record by id  """
#   queryset = Place.objects.all()
#   serializer_class = PlaceSerializer
#   renderer_classes = [PrettyJsonRenderer]
#
#   permission_classes = [permissions.IsAuthenticatedOrReadOnly,IsOwnerOrReadOnly]
#   authentication_classes = [SessionAuthentication]
#
#   def get_serializer_context(self):
#     # collection id is passed from place collection browse
#     context = super().get_serializer_context()
#     context["query_params"] = self.request.query_params
#     return context

class PlacesDetailAPIView(View):
    """  returns serialized multiple database place records by id  """

    def get(self, request, pk_list=None, pk=None):

        cid = request.GET.get('cid')

        if pk_list is not None:
            # Split the string of IDs using the delimiter "-"
            ids = pk_list.split("-")
        elif pk is not None:
            ids = [str(pk)]
        else:
            pass

        places = Place.objects.filter(id__in=ids)

        def sort_unique(arr, key=None, sort_key=None):
            unique_items = []
            seen_items = set()

            for item in arr:
                item_unique = item[key] if key else json.dumps(item)
                if item_unique not in seen_items:
                    unique_items.append(item)
                    seen_items.add(item_unique)

            sort_key = sort_key or key
            if sort_key:
                unique_items.sort(key=lambda x: x[sort_key])

            return unique_items

        with open(os.path.join(settings.STATIC_ROOT, 'aliases.json')) as json_file:
            json_data = json_file.read()
        base_urls = json.loads('{'+json_data+'}')['base_urls'] # Wrap the contents in {} to create a valid JSON object

        def add_urls(data):
            return [
                {**item, 'url': identifier.join(':') if identifier[0].startswith("http") else base_urls.get(identifier[0], '') + identifier[1]}
                if identifier and (base_url := base_urls.get(identifier[0])) is not None
                else item
                for item in data
                for identifier in [item.get('identifier', '').split(':')]
                if len(identifier) == 2 or not item.get('identifier')
            ]

        # Serialize the Place records
        serialized_places = []
        attestation_years = set()
        for place in places:
            # Pass the request in the serializer context
            serializer = PlaceSerializer(place, context={'cid': cid, 'request': request})
            serialized_places.append(serializer.data)
            if place.attestation_year:
                attestation_years.add(place.attestation_year)

        # Calculate the overall extent
        aggregated_extent = None
        for place in serialized_places:
            extent = place["extent"]
            if extent:
                polygon = Polygon.from_bbox(extent)
                aggregated_extent = aggregated_extent.union(polygon) if aggregated_extent else polygon

        # Convert the overall extent to the format expected in the JSON response
        aggregated_extent = aggregated_extent.extent if aggregated_extent else None

        dataset_ids = set([place["dataset_id"] for place in serialized_places])

        # Extract the minmax values and filter out empty lists
        #minmax_values = [(place.get("minmax", [None, None])[0], place.get("minmax", [None, None])[1]) for place in serialized_places]
        minmax_values = [(place.get("minmax", [None, None])[0], place.get("minmax", [None, None])[1]) if place.get("minmax") is not None else (None, None) for place in serialized_places]

        # Filter out None values
        min_values = [value[0] for value in minmax_values if value[0] is not None]
        max_values = [value[1] for value in minmax_values if value[1] is not None]
        # Calculate the min and max values, handling the case of empty sequences
        min_value = min(min_values, default=None)
        max_value = max(max_values, default=None)

        country_codes_mapping = {country['id']: country['text'] for item in json.load(open('media/data/regions_countries.json')) if item.get('text') == 'Countries' for country in item.get('children', [])}
        unique_country_codes = {ccode for place in serialized_places for ccode in place.get("ccodes", [])}
        countries_with_labels = [{ 'ccode': ccode, 'label': country_codes_mapping.get(ccode, '') } for ccode in unique_country_codes]

        # Aggregate places into a single object
        aggregated_place = {
            "id": "-".join(ids),  # Concatenate the IDs,
            "traces": [trace for place in serialized_places for trace in place["traces"]],
            "datasets": sort_unique(list(Dataset.objects.filter(id__in=dataset_ids).values("id", "title")), 'title'),
            "title": "|".join(set(place["title"] for place in serialized_places)),
            "names": sort_unique([name for place in serialized_places for name in place["names"]], 'toponym'),
            "types": add_urls(sort_unique([type for place in serialized_places for type in place["types"]], 'label')),
            "geoms": [geom for place in serialized_places for geom in place["geoms"]],
            "extent": aggregated_extent,
            "links": add_urls(sort_unique([link for place in serialized_places for link in place["links"]], sort_key='identifier')),
            "related": sort_unique([related for place in serialized_places for related in place["related"]], 'label'),
            "descriptions": add_urls(sort_unique([description for place in serialized_places for description in place["descriptions"]], 'value')),
            "depictions": sort_unique([depiction for place in serialized_places for depiction in place["depictions"]]),
            "minmax": [min_value, max_value],
            "countries": sorted(countries_with_labels, key=lambda x: x['ccode']),
            "attestation_years": sorted(attestation_years),
            # "whens": {
            #     "timespans": sort_unique([timespan for place in serialized_places for when in place.get("whens", []) for timespan in when.get("timespans", [])]),
            #     "periods": sort_unique([period for place in serialized_places for when in place.get("whens", []) for period in when.get("periods", [])]),
            #     "label": "|".join(set(when.get("label", "") for place in serialized_places for when in place.get("whens", []) if when.get("label", ""))),
            #     "duration": "|".join(set(when.get("duration", "") for place in serialized_places for when in place.get("whens", []) if when.get("duration", ""))),
            # },
        }

        return JsonResponse(aggregated_place, safe=False)

"""
    place_compare/<int:pk>/
    uses: ds_update()
    "partial database record by place_id for update comparisons"
"""
class PlaceCompareAPIView(generics.RetrieveAPIView):
  """  returns single serialized database place record by id  """
  queryset = Place.objects.all()
  serializer_class = PlaceCompareSerializer
  renderer_classes = [PrettyJsonRenderer]

  permission_classes = [permissions.IsAuthenticatedOrReadOnly,IsOwnerOrReadOnly]
  authentication_classes = [SessionAuthentication]

"""
    place/<str:dslabel>/<str:src_id>/
    published record by dataset label and src_id
"""
class PlaceDetailSourceAPIView(generics.RetrieveAPIView):
  """  single database place record by src_id  """
  queryset = Place.objects.all()
  serializer_class = PlaceSerializer
  renderer_classes = [PrettyJsonRenderer]

  lookup_field = 'src_id'
  permission_classes = [permissions.IsAuthenticatedOrReadOnly,IsOwnerOrReadOnly]
  authentication_classes = [SessionAuthentication]

"""
    /api/geoms?ds={{ ds.label }}}
    /api/geoms?coll={{ coll.id }}}
    in ds_browse and ds_places for all geoms if < 15k
    TODO: this needs refactor (make collection.geometries @property?)
"""
class GeomViewSet(viewsets.ModelViewSet):
  queryset = PlaceGeom.objects.all()
  serializer_class = PlaceGeomSerializer
  #pagination_class = None
  permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

  def get_queryset(self):
    # PlaceGeom objects do not have dataset id or label :^(
    if 'ds' in self.request.GET:
      dslabel = self.request.GET.get('ds')
      dsPlaceIds = Place.objects.values('id').filter(dataset = dslabel)
      qs = PlaceGeom.objects.filter(place_id__in=dsPlaceIds)
    elif 'coll' in self.request.GET:
      cid = self.request.GET.get('coll')
      coll = Collection.objects.get(id=cid)
      collPlaceIds = [p.id for p in coll.places.all()]
      # leaves out polygons and linestrings
      qs = PlaceGeom.objects.filter(
        place_id__in=collPlaceIds,
        jsonb__type__icontains='Point')
    return qs

"""
    /api/geojson/{{ ds.id }}
"""
#class GeoJSONViewSet(viewsets.ModelViewSet):
class GeoJSONAPIView(generics.ListAPIView):
  # use: api/geojson
  #queryset = PlaceGeom.objects.all()
  #serializer_class = GeoJsonSerializer
  serializer_class = FeatureSerializer
  permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

  def get_queryset(self, format=None, *args, **kwargs):
    print('GeoJSONViewSet request.GET',self.request.GET)
    print('GeoJSONViewSet args, kwargs',args, kwargs)
    if 'id' in self.request.GET:
      dsid = self.request.GET.get('id')
      dslabel = get_object_or_404(Dataset, pk=dsid).label
      dsPlaceIds = Place.objects.values('id').filter(dataset = dslabel)
      qs = PlaceGeom.objects.filter(place_id__in=dsPlaceIds)
    elif 'coll' in self.request.GET:
      cid = self.request.GET.get('coll')
      coll = Collection.objects.get(id=cid)
      collPlaceIds = [p.id for p in coll.places.all()]
      qs = PlaceGeom.objects.filter(place_id__in=collPlaceIds,jsonb__type='Point')
    #print('qs',qs)
    return qs

"""
    /api/featureCollection/{{ ds.id  or coll.cid}}
"""
class featureCollectionAPIView(generics.ListAPIView):
  permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

  @extend_schema( # Not intended as a public API
        exclude=True,
  )
  def get(self, format=None, *args, **kwargs):

    mode = self.request.GET.get('mode', 'default') or 'default'
    featureCollection = None

    if 'id' in self.request.GET:
        dsid = self.request.GET.get('id')
        datacollection = get_object_or_404(Dataset, pk=dsid)
        tilesetquery = {"type": "datasets", "id": dsid}
        pass
    elif 'coll' in self.request.GET:
        cid = self.request.GET.get('coll')
        datacollection = get_object_or_404(Collection, id=cid)
        tilesetquery = {"type": "collections", "id": cid}
        pass
    else:
        return Response({"error": "QueryString must include either an id or coll identifier"}, status=status.HTTP_400_BAD_REQUEST)

    # Test for existence of a corresponding tileset
    tiler_url = os.environ.get('TILER_URL') # Must be set in /.env/.dev-whg3
    response = requests.post(tiler_url, json={"getTilesets": tilesetquery})
    if response.status_code == 200:
        available_tilesets = response.json().get('tilesets', [])
        if len(available_tilesets) > 0: # Remove features and return tileset name(s) instead
            featureCollection = {
              "type": "FeatureCollection",
              "mode": mode,
              "features": None,
              "tilesets": available_tilesets
            }
            return JsonResponse(featureCollection, content_type="application/json")

    if mode == 'clusterhull':
        featureCollection = datacollection.clustered_geometries
        pass
    elif mode == 'heatmap':
        featureCollection = datacollection.heatmapped_geometries
        pass
    elif mode == 'convexhull':
        featureCollection = datacollection.hull_geometries
        pass
    elif mode == 'default':
        featureCollection = datacollection.feature_collection
        pass
    else:
        return Response({"error": "Invalid QueryString"}, status=status.HTTP_400_BAD_REQUEST)

    return JsonResponse(featureCollection, content_type="application/json")

"""
    populates drf table in ds_browse.html, ds_places.html
"""
class PlaceTableViewSet(viewsets.ModelViewSet):
  # print('hit PlaceTableViewSet()')
  serializer_class = PlaceTableSerializer
  permission_classes = (permissions.IsAuthenticatedOrReadOnly)

  """
    q: query string
    ds: dataset
  """
  def get_queryset(self):
    ds = get_object_or_404(Dataset, label=self.request.GET.get('ds'))
    # qs = ds.places.all().order_by('place_id')
    qs = ds.places.all().order_by('id')
    # qs = ds.places.all()
    query = self.request.GET.get('q')
    if query is not None:
      qs = qs.filter(title__istartswith=query)
    return qs

  def get_permissions(self):
    """
    Instantiates and returns the list of permissions that this view requires.
    """
    if self.action in ['list','retrieve']:
      print(self.action)
      permission_classes = [permissions.AllowAny]
    else:
      permission_classes = [permissions.IsAdminUser]
    return [permission() for permission in permission_classes]

"""
    populates drf table in collection.collection_places.html
"""
class PlaceTableCollViewSet(viewsets.ModelViewSet):

  serializer_class = PlaceTableSerializer
  permission_classes = (permissions.IsAuthenticatedOrReadOnly)

  """
    q: query string
    coll: collection
  """
  def get_queryset(self):
    # print('PlaceTableCollViewSet() path', self.request.META['PATH_INFO'])
    # /api/placetable_coll/
    # a q value if it's a search on the table
    query = self.request.GET.get('q')
    id_ = self.request.GET.get('id')
    from django.db.models import Min, Max
    coll = get_object_or_404(Collection, id=id_)
    if coll.collection_class == 'dataset':
      qs = coll.places_all
    else:
      qs = coll.places.annotate(seq=Min('annos__sequence')).order_by('seq')
    # qs = coll.places.annotate(seq=Min('collplace__sequence')).order_by('seq')
    # print('qs from PlaceTableCollViewSet()', qs)
    if query is not None:
      qs = qs.filter(title__istartswith=query)
    return qs

  def get_permissions(self):
    """
    Instantiates and returns the list of permissions that this view requires.
    """
    if self.action in ['list','retrieve']:
      print(self.action)
      permission_classes = [permissions.AllowAny]
    else:
      permission_classes = [permissions.IsAdminUser]
    return [permission() for permission in permission_classes]


"""
  areas/

"""
# simple objects for dropdown
class AreaListView(View):
  @staticmethod
  def get(request):
    # print('area_list() request.user',request.user, type(request.user))
    # print('area_list() request.user',str(request.user))
    userstr = str(request.user)
    if isinstance(request.user, AnonymousUser):
      qs = Area.objects.all().filter(Q(type__in=('predefined','country'))).values('id','title','type')
    else:
      user = request.user
      qs = Area.objects.all().filter(Q(type__in=('predefined','country'))| Q(owner=user)).values('id','title','type')
    area_list = []
    for a in qs:
      area = {"id":a['id'],"title":a['title'],"type":a['type']}
      area_list.append(area)

    return JsonResponse(area_list, safe=False)

# simple objects for dropdown
class AreaListAllView(View):
  @staticmethod
  def get(request):
    print('area_list() request',request)
    user = request.user
    area_list = []
    #qs = Area.objects.all().filter(Q(type='predefined')| Q(owner=request.user)).values('id','title','type')
    qs = Area.objects.all().filter(Q(type__in=('predefined','country'))| Q(owner=request.user)).values('id','title','type')
    for a in qs:
      area = {"id":a['id'],"title":a['title'],"type":a['type']}
      area_list.append(area)

    return JsonResponse(area_list, safe=False)


"""
    area/<int:pk>/
    in dataset.html#addtask
"""
class AreaViewSet(viewsets.ModelViewSet):
  queryset = Area.objects.all().order_by('title')
  serializer_class = AreaSerializer

"""
    regions/
    in dataset.html#addtask
"""
class RegionViewSet(View):
  queryset = Area.objects.filter(
      description='UN Statistical Division Sub-Region').order_by('title')
  serializer_class = AreaSerializer


# Country Geometries from ccode list
class CountryFeaturesAPIView(View):
    @extend_schema( # Not intended as a public API
        exclude=True,
    )
    def get(self, request, *args, **kwargs):
        country_codes_param = self.request.GET.get('country_codes', '')
        country_codes = [code.strip().upper() for code in country_codes_param.split(',') if code.strip()]

        countries = Area.objects.filter(Q(type='country') & Q(ccodes__overlap=country_codes)).values('id', 'ccodes', 'geojson')

        country_feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        for country in countries:
            feature = {
                'type': 'Feature',
                'properties': {'ccode': country['ccodes'][0]},
                'geometry': country['geojson']
            }
            country_feature_collection['features'].append(feature)

        return JsonResponse(country_feature_collection, safe=False)

# Fetch Watershed GeoJSON from remote URL
class WatershedAPIView(APIView):
    @extend_schema( # Not intended as a public API
        exclude=True,
    )
    def get(self, request, *args, **kwargs):
        lat = request.query_params.get('lat', None)
        lng = request.query_params.get('lng', None)

        if lat is None or lng is None:
            raise Http404("Latitude and longitude parameters are required.")

        # Construct the URL to fetch watershed GeoJSON
        watershed_url = f"https://mghydro.com/app/watershed_api?lat={lat}&lng={lng}&precision=high"

        try:
            response = requests.get(watershed_url)
            response.raise_for_status()  # Raise an exception for non-200 status codes
            watershed_geojson = response.json()

            # Add attribution
            attribution = "Watershed: MERIT Hydro & Matthew Heberger"
            watershed_geojson['attribution'] = attribution

        except requests.RequestException as e:
            # Handle request errors
            raise Http404(f"Error fetching watershed GeoJSON: {str(e)}")

        return Response(watershed_geojson)
