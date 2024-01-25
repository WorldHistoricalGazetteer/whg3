# main.views
from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, BadHeaderError
from django.db.models import Max
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect #, render_to_response
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from areas.models import Area
from collection.models import Collection, CollectionGroup, CollectionGroupUser
from datasets.models import Dataset
from datasets.tasks import testAdd
from main.models import Link
from places.models import Place, PlaceGeom
from bootstrap_modal_forms.generic import BSModalCreateView
from django.core import serializers
from django.contrib.gis.geos import GEOSGeometry
import json
import random

from .forms import CommentModalForm, ContactForm
es = settings.ES_CONN
from random import shuffle
from urllib.parse import urlparse
import sys

from django.shortcuts import render, redirect
from django import forms
from django.contrib import messages

import requests
import json

# initiated by main.tasks.request_tileset()
def send_tileset_request(dataset_id=None, collection_id=None, tiletype='normal'):
  print("sending a POST request to TILER_URL", dataset_id, collection_id, tiletype)
  # Construct the URL and data payload
  url = settings.TILER_URL
  if dataset_id:
    geoJSONUrl = f"https://dev.whgazetteer.org/datasets/{dataset_id}/mapdata/?variant=tileset"
  elif collection_id:
    geoJSONUrl = f"https://dev.whgazetteer.org/collections/{collection_id}/mapdata/?variant=tileset"
  else:
    raise ValueError("Either dataset_id or collection_id must be provided.")

  print('geoJSONUrl', geoJSONUrl)

  data = {
    "geoJSONUrl": geoJSONUrl,
    "tilesetType": tiletype,
  }
  # Send the POST request
  response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data))

  # Check the response7
  print("Response:", response)
  print("Response status:", response.status_code)
  if response.status_code == 200:
    response_data = response.json()
    if response_data.get("status") == "success":
      print("Tileset created successfully.")
      return {"status": "success", "data": response_data}
    else:
      print("Failed to create tileset:", response_data.get("message"))
      return {"status": "failure", "message": response_data.get("message")}
  else:
    print("Failed to send request:", response.status_code)
    return {"status": "failure", "message": f"Failed to send request: {response.status_code}"}

# {	"status":"success",
# 	"message":"Tileset created.",
# 	"command":"tippecanoe -o /srv/tileserver/tiles/datasets/40.mbtiles -f -n \"datasets-40\" -A \"Atlas of Mutual Heritage: Rombert Stapel\" -l \"features\" -B 4 -rg 10 -al -ap -zg -ac --no-tile-size-limit /srv/tiler/temp/18e6bb6e-635d-45e3-9833-10fe00f686f1.geojson"
# }

# Mixin for checking splash screen pass
class SplashCheckMixin:
  def dispatch(self, request, *args, **kwargs):
    if not request.session.get('passed_splash'):
      return HttpResponseRedirect('/splash')  # Redirect to splash
    return super().dispatch(request, *args, **kwargs)

class Home30a(TemplateView):
  template_name = 'main/home_v30a.html'

  def get_context_data(self, *args, **kwargs):
    context = super(Home30a, self).get_context_data(*args, **kwargs)

    carousel_metadata = []
    for dataset_types in [Collection, Dataset]:
      featured = dataset_types.objects.exclude(featured__isnull=True)
      for dataset in featured:
        carousel_metadata.append(dataset.carousel_metadata)
    random.shuffle(carousel_metadata)
    context['carousel_metadata'] = json.dumps(carousel_metadata)

    context['mbtokenkg'] = settings.MAPBOX_TOKEN_KG
    context['mbtokenmb'] = settings.MAPBOX_TOKEN_MB
    context['mbtokenwhg'] = settings.MAPBOX_TOKEN_WHG
    context['maptilerkey'] = settings.MAPTILER_KEY
    context['media_url'] = settings.MEDIA_URL
    context['base_dir'] = settings.BASE_DIR
    context['es_whg'] = settings.ES_WHG
    context['beta_or_better'] = True if self.request.user.groups.filter(
      name__in=['beta', 'admins']).exists() else False
    context['teacher'] = True if self.request.user.groups.filter(
      name__in=['teacher']).exists() else False
    context['count'] = Place.objects.filter(dataset__public=True).count()

    # TODO: REMOVE THE FOLLOWING? ****************************************************
    # Serialize the querysets to JSON
    f_collections = Collection.objects.exclude(featured__isnull=True)
    f_datasets = Dataset.objects.exclude(featured__isnull=True)
    context['featured_coll'] = f_collections
    context['featured_ds'] = f_datasets

    return context


def get_objects_for_user(model, user, filter_criteria, is_admin=False, extra_filters=None):
  from django.db.models import Max
  # Always apply extra filters if they are provided and the model is Area
  if extra_filters and model == Area:
    objects = model.objects.filter(**extra_filters)
  elif is_admin:
    objects = model.objects.all()
  else:
    objects = model.objects.filter(**filter_criteria).exclude(title__startswith='(stub)')

  # If the user is an admin and we're looking at Area, apply the study_areas filter to all users including admins
  if is_admin and model == Area:
    objects = objects.exclude(type__in=filter_criteria['type'])
  elif model == Dataset: # reverse sort, and some dummy datasets need to be filtered
      objects = objects.exclude(title__startswith='(stub)').order_by()
      objects = objects.annotate(recent_log_timestamp=Max('log__timestamp'))
      objects = objects.order_by('-recent_log_timestamp')

  return objects


def area_list(request):
  # Filter that applies to all Area objects to exclude system records.
  area_filters = {'type__in': ['ccodes', 'copied', 'drawn']}

  # Check if the user is an admin to determine visibility scope.
  is_admin = request.user.groups.filter(name='whg_admins').exists()

  if is_admin:
    # Admins see all Areas matching the filtered types without the owner filter.
    user_areas = Area.objects.filter(**area_filters)
  else:
    # Non-admins see only their Areas matching the filtered types.
    user_areas = Area.objects.filter(**area_filters, owner=request.user)

  return render(request, 'lists/area_list.html', {'areas': user_areas, 'is_admin': is_admin, 'section': 'areas'})

def dataset_list(request):
  is_admin = request.user.groups.filter(name='whg_admins').exists()
  user_datasets = get_objects_for_user(Dataset, request.user, {'owner': request.user}, is_admin)
  return render(request, 'lists/dataset_list.html',
                {'datasets': user_datasets, 'is_admin': is_admin, 'section': 'datasets'})

def collection_list(request, *args, **kwargs):
  print('collection_list() kwargs', kwargs)
  collection_class = kwargs.get('collection_class')
  is_admin = request.user.groups.filter(name='whg_admins').exists()

  if is_admin:
    # Admins see all Collections of the specified class
    user_collections = Collection.objects.filter(collection_class=collection_class)
  else:
    # Non-admins see only their Collections of the specified class
    user_collections = Collection.objects.filter(collection_class=collection_class,
                                                 owner=request.user)

  user_collections = user_collections.annotate(recent_log_timestamp=Max('log__timestamp'))
  user_collections = user_collections.order_by('-recent_log_timestamp')

  return render(request, 'lists/collection_list.html',
                {'collections': user_collections, 'is_admin': is_admin, 'section': 'collections'})

def group_list(request, role):
  user = request.user
  is_admin = request.user.groups.filter(name='whg_admins').exists()
  # Check for admin
  # if user.groups.filter(name='whg_admins').exists() or user.is_superuser:
  if is_admin or user.is_superuser:
    groups = CollectionGroup.objects.all()
    # return early
    context = {'groups': groups, 'is_admin': is_admin, 'section': 'groups'}
    return render(request, 'lists//group_list.html', context)

  # This will fetch groups where the user is a member
  member_groups = CollectionGroup.objects.filter(members__user=user)

  # If they are a leader, add the groups they own
  if role == 'leader':
    owned_groups = CollectionGroup.objects.filter(owner=user)
    groups = (owned_groups | member_groups).distinct()
  else:
    groups = member_groups.distinct()

  context = {
    'groups': groups,
    'role': role,
    'is_admin': is_admin,
    'section': 'groups'
  }
  return render(request, 'lists/group_list.html', context)

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

# get's the correct view based on user group
@login_required
def dashboard_redirect(request):
    if request.user.groups.filter(name='whg_admins').exists():
        return redirect('dashboard-admin')
    else:
        return redirect('dashboard-user')

# for non-admins
@login_required
def dashboard_user_view(request):
  user=request.user
  is_admin = user.groups.filter(name='whg_admins').exists()
  is_leader = user.groups.filter(name='group_leaders').exists()
  django_groups = [group.name for group in user.groups.all()]

  user_datasets_count = Dataset.objects.filter(owner=user.id).count()
  user_collections_count = Collection.objects.filter(owner=user).count()
  user_areas_count = Area.objects.filter(owner=user).count()

  section = request.GET.get('section')

  datasets = get_objects_for_user(Dataset, request.user, {'owner': user}, is_admin)
  collections = get_objects_for_user(Collection, request.user, {'owner': user}, is_admin)
  areas = get_objects_for_user(Area, request.user, {'owner': user}, is_admin)
  groups_member = CollectionGroup.objects.filter(members__user=user)
  groups_led = CollectionGroup.objects.filter(owner=user)

  context = {
    'datasets': datasets,
    'collections': collections,
    'areas': areas,
    'has_datasets': user_datasets_count > 0,
    'has_collections': user_collections_count > 0,
    'has_areas': user_areas_count > 0,
    'section': section,
    'django_groups': django_groups,
    'groups_member': groups_member,
    'groups_led': groups_led,
    'is_admin': is_admin,
    'is_leader': is_leader,
    'box_titles': ['Datasets', 'Place Collections', 'Dataset Collections', 'Study Areas', 'Groups'],

  }
  return render(request, 'main/dashboard_user.html', context)

# all-purpose for admins
# login required decorator in urls.py
@login_required
def dashboard_admin_view(request):
  print('request.GET', request.GET)
  user = request.user
  is_admin = user.groups.filter(name='whg_admins').exists()
  is_leader = user.groups.filter(name='group_leaders').exists()
  django_groups = [group.name for group in user.groups.all()]


  user_datasets_count = Dataset.objects.filter(owner=user.id).count()
  user_collections_count = Collection.objects.filter(owner=user).count()
  user_collections_count = Collection.objects.filter(owner=user).count()

  # section = request.GET.get('section')
  section = request.GET.get('section', 'datasets')

  # TODO: for admins, show all datasets, collections, areas
  datasets = get_objects_for_user(Dataset, request.user, {}, is_admin)
  collections = get_objects_for_user(Collection, request.user, {}, is_admin)
  areas = get_objects_for_user(Area, request.user, {'type': ['predefined', 'country']}, is_admin)
  groups_member = CollectionGroup.objects.filter(members__user=user)
  groups_led = CollectionGroup.objects.filter(owner=user)

  context = {
    'datasets': datasets,
    'collections': collections,
    'areas': areas,
    'has_datasets': user_datasets_count > 0,
    'has_collections': user_collections_count > 0,
    'section': section,
    'django_groups': django_groups,
    'groups_member': groups_member,
    'groups_led': groups_led,
    'is_admin': is_admin,
    'is_leader': is_leader,
  }
  # return render(request, 'main/dashboard_admin.html', {'initial_section': section})
  return render(request, 'main/dashboard_admin.html', context)

# first take at a dashboard for all users
def dashboard_view(request):
  is_admin = request.user.groups.filter(name='whg_admins').exists()
  is_leader = request.user.groups.filter(name='group_leaders').exists()
  user_groups = [group.name for group in request.user.groups.all()]

  user_datasets_count = Dataset.objects.filter(owner=request.user.id).count()
  user_collections_count = Collection.objects.filter(owner=request.user).count()

  section = request.GET.get('section', 'datasets')

  datasets = get_objects_for_user(Dataset, request.user, {'owner': request.user}, is_admin)
  collections = get_objects_for_user(Collection, request.user, {'owner': request.user}, is_admin)

  context = {
    'datasets': datasets,
    'collections': collections,
    'has_datasets': user_datasets_count > 0,
    'has_collections': user_collections_count > 0,
    'section': section,
    'user_groups': user_groups,
    'is_admin': is_admin,
    'is_leader': is_leader,
  }
  return render(request, 'main/dashboard.html', context)

@csrf_exempt
def home_modal(request):
  page = request.POST['page']
  context = {'v1': 'hello there'}
  url = 'home/' + page + '.html'
  print('home_modal() url:', url)
  return render(request, url, context)


def custom_error_view(request, exception=None):
    print('error request', request.GET.__dict__)
    return render(request, "main/500.html", {'error':'fubar'})

def is_url(url):
  try:
    result = urlparse(url)
    return all([result.scheme, result.netloc])
  except ValueError:
    return False

""" 
  create link associated with instance of various models, so far:
  Collection, CollectionGroup, TraceAnnotation, Place 
"""
def create_link(request, *args, **kwargs):
  if request.method == 'POST':
    print('main.create_link() request.POST', request.POST)
    model = request.POST['model']
    objectid = request.POST['objectid']

    uri = request.POST['uri']
    if not is_url(uri):
      return JsonResponse({'status': 'failed', 'result': 'bad uri'}, safe=False)

    label = request.POST['label']
    link_type = request.POST['link_type']
    # license = request.POST['license']

    # Collection or CollectionGroup
    # from django.apps import apps
    Model = apps.get_model(f"collection.{model}")
    print('Model', Model)
    model_str=model.lower() if model == 'Collection' else 'collection_group'
    obj = Model.objects.get(id=objectid)
    gotlink = obj.related_links.filter(uri=uri)
    # gotlink = obj.links.filter(uri=uri)
    print('model_str, obj, gotlink', model_str, obj, gotlink)
    status, msg = ['','']
    # columns in Links table
    # collection_id, collection_group_id, trace_annotation_id, place_id
    if not gotlink:
      print('not got_link')
      try:
        link=Link.objects.create(
          **{model_str:obj}, # instance identifier
          uri = uri,
          label = label,
          link_type = link_type
        )
        result = {'uri': link.uri, 'label': link.label,
                  'link_type':link.link_type,
                  'link_icon':link.get_link_type_display(),
                  'id':link.id}
        status="ok"
      except:
        print('failed', sys.exc_info())
        status = "failed"
        result = "Link *not* created...why?"
    else:
      result = 'dupe'
    return JsonResponse({'status': status, 'result': result}, safe=False)

def remove_link(request, *args, **kwargs):
  #print('kwargs', kwargs)
  link = Link.objects.get(id=kwargs['id'])
  # link = CollectionLink.objects.get(id=kwargs['id'])
  print('remove_link()', link)
  link.delete()
  return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


# TODO on cron in v3?
def statusView(request):
    context = {"status_site": "??",
               "status_database": "??",
               "status_index": "??"}

    # database
    try:
        place = get_object_or_404(Place, id=81011)
        context["status_database"] = "up" if place.title == 'Abydos' else 'error'
    except:
        context["status_database"] = "down"

    # celery recon task
    try:
        result = testAdd.delay(8, 8)
        context["status_tasks"] = "up" if result.get() == 16 else 'error'
    except:
        context["status_tasks"] = "down"

    return render(request, "main/status.html", {"context": context})


def contactView(request):
    print('contact request.GET', request.GET)
    sending_url = request.GET.get('from')
    if request.method == 'GET':
        form = ContactForm()
    else:
        form = ContactForm(request.POST)
        if form.is_valid():
            human = True
            name = form.cleaned_data['name']
            username = form.cleaned_data['name'] # hidden input
            subject = form.cleaned_data['subject']
            from_email = form.cleaned_data['from_email']
            message = name +'('+from_email+'), on the subject of '+subject+' says: \n\n'+form.cleaned_data['message']
            subject_reply = "WHG message received"
            message_reply = '\nWe received your message concerning "'+subject+'" and will respond soon.\n\n regards,\nThe WHG project team'
            try:
                send_mail(subject, message, from_email, ["karl@kgeographer.org"])
                send_mail(subject_reply, message_reply, 'karl@kgeographer.org', [from_email])
            except BadHeaderError:
                return HttpResponse('Invalid header found.')
            return redirect('/success?return='+sending_url if sending_url else '/')
            # return redirect(sending_url)
        else:
            print('not valid, why?')
                
    return render(request, "main/contact.html", {'form': form, 'user': request.user})


def contactSuccessView(request, *args, **kwargs):
    returnurl = request.GET.get('return')
    print('return, request', returnurl, str(request.GET))
    return HttpResponse(
        '<div style="font-family:sans-serif;margin-top:3rem; width:50%; margin-left:auto; margin-right:auto;"><h4>Thank you for your message! We will reply soon.</h4><p><a href="'+returnurl+'">Return</a><p></div>')


class CommentCreateView(BSModalCreateView):
    template_name = 'main/create_comment.html'
    form_class = CommentModalForm
    success_message = 'Success: Comment was created.'
    success_url = reverse_lazy('')

    def form_valid(self, form, **kwargs):
        form.instance.user = self.request.user
        place = get_object_or_404(Place, id=self.kwargs['rec_id'])
        form.instance.place_id = place
        return super(CommentCreateView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super(CommentCreateView, self).get_context_data(*args, **kwargs)
        context['place_id'] = self.kwargs['rec_id']
        return context

    # ** ADDED for referrer redirect
    def get_form_kwargs(self, **kwargs):
        kwargs = super(CommentCreateView, self).get_form_kwargs()
        redirect = self.request.GET.get('next')
        print('redirect in get_form_kwargs():', redirect)
        if redirect is not None:
            self.success_url = redirect
        else:
            self.success_url = '/mydata'
        # print('cleaned_data in get_form_kwargs()',form.cleaned_data)
        if redirect:
            if 'initial' in kwargs.keys():
                kwargs['initial'].update({'next': redirect})
            else:
                kwargs['initial'] = {'next': redirect}
        print('kwargs in get_form_kwargs():', kwargs)
        return kwargs
    # ** END
