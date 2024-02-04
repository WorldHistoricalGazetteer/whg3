# main.views
from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.mail import send_mail, BadHeaderError
from django.db.models import Max, Count, Case, When
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect #, render_to_response
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView

from .forms import CommentModalForm, ContactForm
from areas.models import Area
from collection.models import Collection, CollectionGroup, CollectionGroupUser
from datasets.models import Dataset
from datasets.tasks import testAdd
from main.models import Link
from places.models import Place, PlaceGeom
from utils.emailing import new_emailer

from bootstrap_modal_forms.generic import BSModalCreateView
import json
import random
import requests
import sys
from urllib.parse import urlparse

es = settings.ES_CONN

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
  default_template_name = 'main/home_v30a.html'

  def get_template_names(self):
    version = self.kwargs.get('version', 'v30a')
    if version == 'v30a2':
      return 'main/home_v30a2.html'
    else:
      return self.default_template_name

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

# used for dashboard_user() and dataset_list()
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

def area_list(request, sort='', order=''):
  is_admin = request.user.groups.filter(name='whg_admins').exists()
  text_fields = ['title', 'description', 'type', 'owner']

  # only user-created areas
  areas = Area.objects.filter(type__in=['ccodes', 'copied', 'drawn'])

  # Apply filters from request if any
  filters = request.GET.get('filters', {})
  if filters:
    pass
  # Logic to apply filters to user_datasets
  # ...

  # Sort based on the parameters
  if sort and order:
    if sort in text_fields:
        # Apply Lower function for text fields
        if order == 'desc':
            areas = areas.order_by(Lower(sort).desc())
        else:
            areas = areas.order_by(Lower(sort))
    else:
        # Standard sorting for non-text fields
        sort_param = f'-{sort}' if order == 'desc' else sort
        areas = areas.order_by(sort_param)
    #
    # if order == 'desc':
    #     areas = areas.order_by(Lower(sort).desc())
    # else:
    #     areas = areas.order_by(Lower(sort))

  return render(request, 'lists/area_list.html', {'areas': areas, 'is_admin': is_admin, 'section': 'areas'})

def dataset_list(request, sort='', order=''):
  filters = request.GET
  print("Request GET parameters:", request.GET)

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  datasets = get_objects_for_user(Dataset, request.user, {'owner': request.user}, is_admin)
  text_fields = ['title', 'label', 'status', 'owner']

  # Sort the datasets based on the parameters
  if sort == 'last_modified':
    if order == 'desc':
      datasets = datasets.annotate(last_log_timestamp=Max('log__timestamp')).order_by('-last_log_timestamp')
    else:
      datasets = datasets.annotate(last_log_timestamp=Max('log__timestamp')).order_by('last_log_timestamp')
  elif sort and order:
    if sort in text_fields:
        # Apply Lower function for text fields
        if order == 'desc':
            datasets = datasets.order_by(Lower(sort).desc())
        else:
            datasets = datasets.order_by(Lower(sort))
    else:
        # Standard sorting for non-text fields
        sort_param = f'-{sort}' if order == 'desc' else sort
        datasets = datasets.order_by(sort_param)

  # Apply filters from request if any
  print("Filters received:", filters)
  if filters:
    if 'ds_status' in filters and filters['ds_status'] != 'all':
      datasets = datasets.filter(ds_status=filters['ds_status'])

    if 'owner' in filters:
      if filters['owner'] == 'staff':
        staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
        datasets = datasets.filter(owner__groups__in=staff_groups)
      elif filters['owner'] == 'contributors':
        staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
        datasets = datasets.exclude(owner__groups__in=staff_groups)

    if 'title' in filters and filters['title']:
      datasets = datasets.filter(title__icontains=filters['title'])

  # Logic to apply filters to user_datasets
  # ...

  return render(request, 'lists/dataset_list.html',
                {'datasets': datasets, 'is_admin': is_admin, 'section': 'datasets'})


def collection_list(request, sort='', order='', **kwargs):
  print('collection_list() kwargs', kwargs)
  # collection_class = kwargs.get('collection_class')
  is_admin = request.user.groups.filter(name='whg_admins').exists()
  text_fields = ['title', 'type', 'status', 'owner']

  if is_admin:
    collections = Collection.objects.all()
  else:
    collections = Collection.objects.filter(owner=request.user)

  collections = collections.annotate(recent_log_timestamp=Max('log__timestamp'))

  collections = collections.annotate(
    count=Case(
      When(collection_class='place', then=Count('annos')),
      When(collection_class='dataset', then=Count('datasets__places')),  # Adjust based on your model relationships
      default=0
    )
  )

  filters = request.GET.get('filters', {})
  if filters:
    pass
  # Logic to apply filters to collections
  # ...

  # Sort based on the parameters
  if sort == 'last_modified':
    if order == 'desc':
      collections = collections.annotate(last_log_timestamp=Max('log__timestamp')).order_by('-last_log_timestamp')
    else:
      collections = collections.annotate(last_log_timestamp=Max('log__timestamp')).order_by('last_log_timestamp')
  elif sort == 'count':
    if order == 'desc':
      collections = collections.order_by('-count')
    else:
      collections = collections.order_by('count')
  elif sort and order:
    if sort in text_fields:
        # Apply Lower function for text fields
        if order == 'desc':
            collections = collections.order_by(Lower(sort).desc())
        else:
            collections = collections.order_by(Lower(sort))
    else:
        # Standard sorting for non-text fields
        sort_param = f'-{sort}' if order == 'desc' else sort
        collections = collections.order_by(sort_param)

    # if order == 'desc':
    #     collections = collections.order_by(Lower(sort).desc())
    # else:
    #     collections = collections.order_by(Lower(sort))


  return render(request, 'lists/collection_list.html',
                {'collections': collections, 'is_admin': is_admin, 'section': 'collections'})

def group_list(request, sort='', order=''):
  is_admin = request.user.groups.filter(name='whg_admins').exists()

  text_fields = ['title', 'category', 'owner']

  if is_admin:
    # Admins see all CollectionGroups
    groups = CollectionGroup.objects.all()
  else:
    # Non-admins see only the CollectionGroups where they are a member
    groups = CollectionGroup.objects.filter(members__user=request.user)

  filters = request.GET.get('filters', {})
  if filters:
    pass
  # Logic to apply filters to groups
  # ...

  if sort and order:
    if sort in text_fields:
        # Apply Lower function for text fields
        if order == 'desc':
            groups = groups.order_by(Lower(sort).desc())
        else:
            groups = groups.order_by(Lower(sort))
    else:
        # Standard sorting for non-text fields
        sort_param = f'-{sort}' if order == 'desc' else sort
        groups = groups.order_by(sort_param)

    # if order == 'desc':
    #     groups = groups.order_by(Lower(sort).desc())
    # else:
    #     groups = groups.order_by(Lower(sort))

  return render(request, 'lists/group_list.html',
                {'groups': groups, 'is_admin': is_admin, 'section': 'groups'})


# gets the correct view based on user group
@login_required
def dashboard_redirect(request):
    if request.user.groups.filter(name='whg_admins').exists():
        return redirect('dashboard-admin')
    else:
        return redirect('dashboard-user')

# all-purpose for admins
@login_required
def dashboard_admin_view(request):
  print('request.GET', request.GET)
  user = request.user
  is_admin = user.groups.filter(name='whg_admins').exists()
  is_leader = user.groups.filter(name='group_leaders').exists()
  django_groups = [group.name for group in user.groups.all()]


  user_datasets_count = Dataset.objects.filter(owner=user.id).count()
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
  # return render(request, 'main/dashboard_admin.html', context)
  return render(request, 'main/dashboard_admin2.html', context)

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

# contact form used throughout
def contact_view(request):
  print('contact_view() request.POST', request.POST)
  sending_url = request.GET.get('from')
  if request.method == 'GET':
    form = ContactForm()
  else:
    form = ContactForm(request.POST)
    if form.is_valid():
      name = form.cleaned_data['name']
      username = form.cleaned_data.get('username', None)
      user_subject = form.cleaned_data['subject']
      user_email = form.cleaned_data['from_email']
      user_message = form.cleaned_data['message']
      try:
        # deliver form message to admins
        print('EMAIL_TO_ADMINS', settings.EMAIL_TO_ADMINS)
        new_emailer(
          email_type='contact_form',
          subject='Contact form submission',
          from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt to admins
          to_email=settings.EMAIL_TO_ADMINS,  # to editor
          reply_to=[user_email],  # reply-to sender
          name=name,  # user's name
          username=username,  # user's username
          user_subject=user_subject,  # user-submitted subject
          user_email=user_email,  # user's email
          user_message=user_message,  # user-submitted message
        )
        # deliver 'received' reply to sender
        new_emailer(
          email_type='contact_reply',
          subject="Message to WHG received",  # got it
          from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt
          to_email=[user_email],  # to sender
          reply_to=[settings.DEFAULT_FROM_EDITORIAL],  # reply-to editorial
          name=name,  # user's name
          greeting_name=name if name else username,
          user_subject=user_subject,  # user-submitted subject
        )
      except BadHeaderError:
        return HttpResponse('Invalid header found.')
      return redirect('/success?return=' + sending_url if sending_url else '/')
    else:
      print('Form errors from contact_view():', form.errors)

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
