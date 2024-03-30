from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
User = get_user_model()
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView
from django.db.models import Count

from datetime import datetime
from elasticsearch8 import Elasticsearch
from collections import Counter
import itertools, re
from django.core.serializers import serialize
from urllib.parse import unquote_plus

from collection.models import Collection
from datasets.models import Dataset
from places.models import Place
from places.utils import attribListFromSet

# write review status = 2 (per authority)
def defer_review(request, pid, auth, last):
  print('defer_review() pid, auth, last', pid, auth, last)
  p = get_object_or_404(Place, pk=pid)
  if auth in ['whg','idx']:
    p.review_whg = 2
  elif auth.startswith('wd'):
    p.review_wd = 2
  else:
    p.review_tgn = 2
  p.save()
  referer = request.META.get('HTTP_REFERER')
  base = re.search('^(.*?)review', referer).group(1)
  print('referer',referer)
  print('last:',int(last))
  if '?page' in referer:
    nextpage=int(referer[-1])+1
    if nextpage < int(last):
      # there's a next record/page
      return_url = referer[:-1] + str(nextpage)
    else:
      return_url = base + 'reconcile'
  else:
    # first page, might also be last for pass
    if int(last) > 1:
      return_url = referer + '?page=2'
    else:
      return_url = base + 'reconcile'
  # return to calling page
  return HttpResponseRedirect(return_url)

class SetCurrentResultView(View):
  def post(self, request, *args, **kwargs):
    place_ids = request.POST.getlist('place_ids')
    print('Setting place_ids in session:', place_ids)
    request.session['current_result'] = {'place_ids': place_ids}
    # messages.success(request, 'Place details loaded successfully!')
    return JsonResponse({'status': 'ok'})

class PlacePortalView(TemplateView):
  template_name = 'places/place_portal.html'

  def get_context_data(self, *args, **kwargs):
    context = super(PlacePortalView, self).get_context_data(*args, **kwargs)
    context['mbtokenkg'] = settings.MAPBOX_TOKEN_KG
    context['mbtokenwhg'] = settings.MAPBOX_TOKEN_WHG
    context['mbtoken'] = settings.MAPBOX_TOKEN_WHG
    context['maptilerkey'] = settings.MAPTILER_KEY

    me = self.request.user
    if not me.is_anonymous:
      if me.groups.filter(name='whg_admins').exists():
        context['my_collections'] = Collection.objects.filter(collection_class='place')
      else:
        context['my_collections'] = Collection.objects.filter(owner=me, collection_class='place')

    context['payload'] = [] # parent and children if any
    context['traces'] = [] #
    context['allts'] = []

    context['core'] = ['ne_countries','ne_rivers982','ne_mountains','wri_lakes']
    
    # Extract any whg_id from a permalink URL
    whg_id = kwargs.get('whg_id', '')    
    # Extract any encoded IDs from a permalink URL
    encoded_ids = kwargs.get('encoded_ids', '')
    if whg_id:
        print('Assembling parent and child place_ids')   
        # TO DO - search ES - in the meantime, fall back to the IDs stored in the session variable
        place_ids = self.request.session.get('current_result', {}).get('place_ids', [])
    elif encoded_ids:
        place_ids = list(map(int, encoded_ids.split(',')))
    else:
        # Fall back to the IDs stored in the session variable
        place_ids = self.request.session.get('current_result', {}).get('place_ids', [])

    place_ids = list(map(int, place_ids))
    print('place_ids in portal.js', place_ids)

    if not place_ids:
        messages.error(self.request, "Place IDs are required to view this page")
        raise Http404("Place IDs are required")

    alltitles = set()
    allvariants = []
    try:
      place_ids = [int(pid) for pid in place_ids]
      qs = Place.objects.filter(id__in=place_ids).order_by('-whens__minmax')
      #context['title'] = qs.first().title
      collections = []
      annotations = []
      all_geoms = []
      print('qs', qs)
      print('place_ids', place_ids)
      for place in qs:
        ds = Dataset.objects.get(id=place.dataset.id)
        print('place.title', place.title)
        alltitles.add(place.title)

        # temporally scoped attributes
        names = attribListFromSet('names', place.names.all(), exclude_title=place.title)
        print('names for a place:', names)
        types = attribListFromSet('types', place.types.all())

        # get traces, collections for this attestation
        attest_traces = list(place.traces.all())
        attest_collections = [t.collection for t in attest_traces if t.collection.status == "published"]

        # add to global list
        annotations = annotations + attest_traces
        collections = list(set(collections + attest_collections))

        # collections = Collection.objects.filter(collection_class="place", places__id__in = place_ids).distinct()

        geoms = [geom.jsonb for geom in place.geoms.all()]
        related = [rel.jsonb for rel in place.related.all()]

        # timespans generated upon Place record creation
        # draws from 'when' in names, types, geoms, relations
        # deliver to template in context
        timespans = list(t for t, _ in itertools.groupby(place.timespans)) if place.timespans else []
        context['allts'] += timespans

        collection_records = []
        for collection in attest_collections:
            collection_url = reverse('collection:place-collection-browse', args=[collection.id])
            collection_record = {
                "class": collection.collection_class,
                "id": collection.id,
                "url": collection_url,
                "title": collection.title,
                "description": collection.description,
                "count": collection.places_all.aggregate(place_count=Count('id'))['place_count']
            }
            collection_records.append(collection_record)

        record = {
          # "whg_id": id_,
          "dataset": {"id": ds.id, "label": ds.label,
                      "name": ds.title, "webpage": ds.webpage},
          "place_id": place.id,
          "src_id": place.src_id,
          "purl": ds.uri_base + str(place.id) if 'whgaz' in ds.uri_base else ds.uri_base + place.src_id,
          "title": place.title,
          "ccodes": place.ccodes,
          "names": names,
          "types": types,
          "geom": geoms,
          "related": related,
          "links": [link.jsonb for link in place.links.distinct('jsonb') if
                    not link.jsonb['identifier'].startswith('whg')],
          "descriptions": [descr.jsonb for descr in place.descriptions.all()],
          "depictions": [depict.jsonb for depict in place.depictions.all()],
          "minmax": place.minmax,
          "timespans": timespans,
          "collections": collection_records
        }
        for name in names:
          variant = name.get('label', '')
          if variant != place.title:
            allvariants.append(variant)

        context['payload'].append(record)
        all_geoms.extend(geoms)
    except ValueError:
      messages.error(self.request, "Invalid place ID format")
      raise Http404("Invalid place ID format")
  
    if all_geoms:
        coordinates_list = [geom['coordinates'] for geom in all_geoms]
        min_x = min(coord[0] for coord in coordinates_list)
        min_y = min(coord[1] for coord in coordinates_list)
        max_x = max(coord[0] for coord in coordinates_list)
        max_y = max(coord[1] for coord in coordinates_list)
        extent = [min_x, min_y, max_x, max_y]
        centroid = [(min_x + max_x) / 2, (min_y + max_y) / 2]
        context['extent'] = extent
        context['centroid'] = centroid

    title_counts = Counter(alltitles)
    variant_counts = Counter(allvariants)

    # Find the two most common titles and variants
    common_titles = [title for title, _ in title_counts.most_common(2)]
    common_variants = [variant for variant, _ in variant_counts.most_common(2)]

    # Construct the portal headword
    portal_headword = common_titles + common_variants
    context['portal_headword'] = "; ".join(portal_headword)+"; ..."
    context['annotations'] = annotations
    context['collections'] = collections

    return context

class PlaceDetailView(DetailView):
  #login_url = '/accounts/login/'
  redirect_field_name = 'redirect_to'
  
  model = Place
  template_name = 'places/place_detail.html'

  
  def get_success_url(self):
    pid = self.kwargs.get("id")
    #user = self.request.user
    #print('messages:', messages.get_messages(self.kwargs))
    return '/places/'+str(pid)+'/detail'

  def get_object(self):
    pid = self.kwargs.get("id")
    return get_object_or_404(Place, id=pid)
  
  def get_context_data(self, *args, **kwargs):
    context = super(PlaceDetailView, self).get_context_data(*args, **kwargs)
    context['mbtokenkg'] = settings.MAPBOX_TOKEN_KG
    context['mbtoken'] = settings.MAPBOX_TOKEN_WHG
    context['maptilerkey'] = settings.MAPTILER_KEY

    print('PlaceDetailView get_context_data() kwargs:',self.kwargs)
    print('PlaceDetailView get_context_data() request.user',self.request.user)
    place = get_object_or_404(Place, pk= self.kwargs.get("id"))
    ds = place.dataset
    me = self.request.user
    #placeset = Place.objects.filter(dataset=ds.label
    
    context['timespans'] = {'ts':place.timespans or None}
    context['minmax'] = {'mm':place.minmax or None}
    context['dataset'] = ds
    context['beta_or_better'] = True if self.request.user.groups.filter(name__in=['beta', 'admins']).exists() else False

    return context

# TODO:  tgn query very slow
class PlaceModalView(DetailView):
  model = Place

  template_name = 'places/place_modal.html'
  redirect_field_name = 'redirect_to'
    
  def get_success_url(self):
    pid = self.kwargs.get("id")
    #user = self.request.user
    return '/places/'+str(pid)+'/modal'

  def get_object(self):
    pid = self.kwargs.get("id")
    return get_object_or_404(Place, id=pid)
  
  def get_context_data(self, *args, **kwargs):
    context = super(PlaceModalView, self).get_context_data(*args, **kwargs)
    context['mbtokenkg'] = settings.MAPBOX_TOKEN_KG
    context['mbtoken'] = settings.MAPBOX_TOKEN_WHG
    context['maptilerkey'] = settings.MAPTILER_KEY

    print('PlaceModalView get_context_data() kwargs:',self.kwargs)
    print('PlaceModalView get_context_data() request.user',self.request.user)
    place = get_object_or_404(Place, pk=self.kwargs.get("id"))
    ds = place.dataset
    dsobj = {"id":ds.id, "label":ds.label, "uri_base":ds.uri_base,
             "title":ds.title, "webpage":ds.webpage, 
             "minmax":None if ds.core else ds.minmax, 
             "creator":ds.creator, "last_modified":ds.last_modified_text} 
    #geomids = [geom.jsonb['properties']['id'] for geom in place.geoms.all()]
    #context['geoms'] = geoms
    context['dataset'] = dsobj
    context['beta_or_better'] = True if self.request.user.groups.filter(name__in=['beta', 'admins']).exists() else False

    return context

  # //
  # given place_id (pid), return abbreviated place_detail
  # //

class PlaceFullView(PlacePortalView):
  def render_to_response(self, context, **response_kwargs):
    return JsonResponse(context, **response_kwargs)




