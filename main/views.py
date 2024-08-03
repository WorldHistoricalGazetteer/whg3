# main.views
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import BadHeaderError
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import escape
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views.generic.base import TemplateView

from .forms import CommentModalForm, ContactForm, AnnouncementForm, VolunteerForm
from areas.models import Area
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)
from collection.models import Collection, CollectionGroup
from datasets.models import Dataset
from datasets.tasks import testAdd
from main.decorators import uber_user_required
from main.tasks import needs_tileset, request_tileset
from .models import Announcement, Link, DownloadFile, Comment
from places.models import Place
from resources.models import Resource
from utils.emailing import new_emailer

from bootstrap_modal_forms.generic import BSModalCreateView
import json
import random
import requests
import sys
from urllib.parse import urlparse
import urllib.parse

es = settings.ES_CONN

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

def health_check(request):
    #TODO: Could be extended to check other aspects of app health, for example: 
    # checks = { # These functions would need to be provided
    #     "database": check_database,
    #     "cache": check_cache,
    #     "external_service": check_external_service,
    #     "disk_space": check_disk_space,
    #     "memory_usage": check_memory_usage,
    #     "cpu_usage": check_cpu_usage
    # }
    #
    # status = "healthy"
    # details = {}
    #
    # for check, func in checks.items():
    #     result, message = func()
    #     details[check] = message
    #     if not result:
    #         status = "unhealthy"
    #
    # return JsonResponse({"status": status, "details": details})    
    
    return JsonResponse({"Status": "healthy"})

def OpenAPIView(request):
    return render(request, 'main/openapi.html', {'schema_url': '/api/schema/'})

def get_task_progress(request, taskid):
    print(f"Requested URL: {request.path}, taskid: {taskid}")
    
    task = AsyncResult(taskid)
    print(f"Task state: {task.state}, task result: {task.result}")
    response_data = {
        'state': task.state,
        'progress': {}
    }
    
    try:
        if task.result:
            response_data['progress'] = {
                'current': task.result.get('current', 0),
                'total': task.result.get('total', 0)
            }
    except ObjectDoesNotExist: # Handle the case where task.result raises DoesNotExist exception
        response_data['progress'] = {
            'current': 0,
            'total': 0
        }
    
    print('Response data:', response_data)
    
    return JsonResponse(response_data)

class AnnouncementListView(ListView):
    model = Announcement
    context_object_name = 'announcements'
    template_name = 'announcements/announcement_list.html'
    queryset = Announcement.objects.filter(active=True).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_whgadmin'] = self.request.user.groups.filter(name='whg_admins').exists()
        return context

class AnnouncementCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'announcements/announcement_form.html'
    success_url = reverse_lazy('announcements-list')
    permission_required = 'main.add_announcement' # Adjust based on your app's name and permissions

class AnnouncementDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Announcement
    template_name = 'announcements/announcement_confirm_delete.html'
    success_url = reverse_lazy('announcements-list')
    permission_required = 'main.delete_announcement' # Adjust based on your app's name and permissions

class AnnouncementUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'announcements/announcement_form.html'
    success_url = reverse_lazy('announcements-list')
    permission_required = 'main.change_announcement' # Adjust based on your app's name and permissions

    def form_valid(self, form):
      if form.is_valid():
        return super().form_valid(form)
      else:
        print(form.errors)
        return self.form_invalid(form)

@method_decorator(uber_user_required, name='dispatch')
class TilesetListView(LoginRequiredMixin, TemplateView):
    template_name = 'main/tools_tilesets.html'
    login_url = '/accounts/login/'

    def dispatch(self, request, *args, **kwargs):
        if request.user.username != "whgadmin":
            return HttpResponseForbidden("You are not authorized to access this page.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch tilesets
        tilesets_url = settings.TILER_URL
        tilesets_data = {"getTilesetsAll": {}}
        tilesets_response = requests.post(tilesets_url, headers={"Content-Type": "application/json"}, data=json.dumps(tilesets_data))
        tilesets = sorted(list(tilesets_response.json()))

        # Fetch datasets and collections
        datasets = Dataset.objects.all().order_by('id')
        collections = Collection.objects.filter(collection_class='place').order_by('id')

        # Create dictionaries to store dataset and collection titles and public statuses
        dataset_titles = {dataset.id: (dataset.title, dataset.public) for dataset in datasets}
        collection_titles = {collection.id: (collection.title, collection.public) for collection in collections}

        # Pass both sets of data to the template
        context['data'] = {
            'datasets': [],
            'collections': []
        }

        # Track the tilesets that have matching datasets or collections
        matched_tilesets = set()

        # Enqueue a Celery task for each category and id
        for category, items in {'datasets': datasets, 'collections': collections}.items():
            for item in items:
                # Check if the tileset exists for the current category and id
                tileset_key = f"{category}-{item.id}"
                has_tileset = tileset_key in tilesets
                if has_tileset:
                    matched_tilesets.add(tileset_key)
                # Enqueue a Celery task for each category and id
                task = needs_tileset.delay(category=category, id=item.id)
                # Add the task id to the context for each category
                context['data'][category].append({
                    'category': category,
                    'id': item.id,
                    'title': item.title,
                    'public': item.public,
                    'has_tileset': has_tileset,
                    'task_id': task.id
                })

        # Identify orphaned tilesets
        orphaned_tilesets = set(tilesets) - matched_tilesets

        # Add orphaned tilesets to the context
        for orphan in orphaned_tilesets:
            category, id = orphan.split('-')
            if category in context['data']:
                context['data'][category].append({
                    'category': category,
                    'id': id,
                    'title': 'Orphaned Tileset',
                    'public': None,  # Orphaned tilesets have no corresponding dataset or collection
                    'has_tileset': True,
                    'task_id': None
                })

        # Flatten the context data lists for rendering in the template
        context['data'] = context['data']['datasets'] + context['data']['collections']

        return context

@login_required
def tileset_generate_view(request, category, id):
    # Ensure that only the user with username "whgadmin" can access this view
    if request.user.is_superuser:  # TODO: change to whg_admins group?
        if request.method == 'GET':
            action = 'generate'
        elif request.method == 'DELETE':
            action = 'delete'
        # task_result = request_tileset.delay(category, id, action)
        # return JsonResponse({'task_id': task_result.id})
        request_tileset(category, id, action)
        return JsonResponse({'task_id': None})
    else:
        return JsonResponse({'error': 'Access forbidden'}, status=403)

# class TilesetGenerateView(LoginRequiredMixin, View):
#     def get(self, request, category, id):
#         # Ensure that only the user with username "whgadmin" can access this view
#         if request.user.username == "whgadmin":
#             action = 'generate'
#             # Perform the tileset generation request
#             request_tileset(category, id, action)
#             return JsonResponse({'task_id': None})
#         else:
#             return JsonResponse({'error': 'Access forbidden'}, status=403)
#
#     def delete(self, request, category, id):
#         # Ensure that only the user with username "whgadmin" can access this view
#         if request.user.username == "whgadmin":
#             action = 'delete'
#             # Perform the tileset deletion request
#             result = request_tileset(category, id, action)
#             return JsonResponse({'result': result})
#         else:
#             return JsonResponse({'error': 'Access forbidden'}, status=403)

# Mixin for checking splash screen pass
class SplashCheckMixin:
  def dispatch(self, request, *args, **kwargs):
    if not request.session.get('passed_splash'):
      return HttpResponseRedirect('/splash')  # Redirect to splash
    return super().dispatch(request, *args, **kwargs)

class Home30a(TemplateView):
  template_name = 'main/home_v30a4.html'

  # def get_template_names(self):
  #   version = self.kwargs.get('version', '30a4')
  #   print(f"get_template_names accessed with version: {version}")
  #   return [f'main/home_v{version}.html']

  def get_context_data(self, *args, **kwargs):
    context = super(Home30a, self).get_context_data(*args, **kwargs)

    carousel_metadata = []
    # rulling out Olaudah; owtrad dataset also an issue
    for dataset_types in [Collection, Dataset]:
      featured = dataset_types.objects.exclude(featured__isnull=True)
      for dataset in featured:
        # print('dataset in views:186', dataset, dataset.id)
        if dataset.id != 50:
          carousel_metadata.append(dataset.carousel_metadata)
    random.shuffle(carousel_metadata)
    context['carousel_metadata'] = json.dumps(carousel_metadata)

    # context['mbtokenkg'] = settings.MAPBOX_TOKEN_KG
    # context['mbtokenmb'] = settings.MAPBOX_TOKEN_MB
    # context['mbtokenwhg'] = settings.MAPBOX_TOKEN_WHG
    #context['maptilerkey'] = settings.MAPTILER_KEY
    context['media_url'] = settings.MEDIA_URL
    context['base_dir'] = settings.BASE_DIR
    context['es_whg'] = settings.ES_WHG
    context['beta_or_better'] = True if self.request.user.groups.filter(
      name__in=['beta', 'admins']).exists() else False
    context['teacher'] = True if self.request.user.groups.filter(
      name__in=['teacher']).exists() else False
    context['count'] = Place.objects.filter(dataset__public=True, dataset__core=True).count()
    context['announcements'] = Announcement.objects.filter(active=True).order_by('-created_at')[:3]
    context['count_places'] = Place.objects.filter(Q(dataset__public=True) | Q(dataset__core=True)).count()

    # TODO: REMOVE THE FOLLOWING? ****************************************************
    # Serialize the querysets to JSON
    f_collections = Collection.objects.exclude(featured__isnull=True)
    f_datasets = Dataset.objects.exclude(featured__isnull=True)
    context['featured_coll'] = f_collections
    context['featured_ds'] = f_datasets

    return context

# TODO: what rules? this or the *_list() functions?
# used for dashboard_user() and dataset_list()
def get_objects_for_user(model, user, filter_criteria, is_admin=False, extra_filters=None):
  print('get_objects_for_user',
        dict(model=model, filter_criteria=filter_criteria, is_admin=is_admin, extra_filters=extra_filters))
  from django.db.models import Q
  collaborator_objects = model.objects.none()

  # Always apply extra filters if they are provided and the model is Area
  if extra_filters and model == Area:
    objects = model.objects.filter(**extra_filters)
  elif is_admin:
    objects = model.objects.all()
  else:
    # Get the objects owned by the user
    owned_objects = model.objects.filter(**filter_criteria).exclude(title__startswith='(stub)')

    # Get the objects where the user is a collaborator
    if model == Dataset:
      collaborator_objects = Dataset.objects.filter(collabs__user_id=user.id)
    elif model == Collection:
      collaborator_objects = Collection.objects.filter(collabs__user_id=user.id)

    # Combine the querysets
    objects = owned_objects | collaborator_objects

  if model == Area:
    objects = objects.filter(type__in=['ccodes', 'copied', 'drawn']).order_by('-created')

  if is_admin and model == Area and 'type' in filter_criteria:
    objects = objects.exclude(type__in=filter_criteria['type'])
  elif model == Dataset:  # reverse sort, and some dummy datasets need to be filtered
    print('model == Dataset')
    objects = objects.exclude(Q(title__startswith='(stub)')|Q(numrows__lt=1)).order_by('-create_date')
    # print('Dataset objects count', objects.count())
    # print('Datasets:', objects)
    # objects = objects.annotate(recent_log_timestamp=Max('log__timestamp'))

  return objects

def area_list(request, sort='', order=''):
  filters = request.GET
  print("area_list() GET (filters):", request.GET)
  print('area_list() sort, order', sort, order)

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  text_fields = ['title', 'description', 'type', 'owner']

  # only user-created areas
  areas = Area.objects.filter(type__in=['ccodes', 'copied', 'drawn'])

 # Sort based on the parameters
  if sort and order:
    if sort == 'owner':
      sort = 'owner__username'
    if sort in text_fields:
        if order == 'desc':
            areas = areas.order_by(Lower(sort).desc())
        else:
            areas = areas.order_by(Lower(sort))
    else:
        sort_param = f'-{sort}' if order == 'desc' else sort
        areas = areas.order_by(sort_param)
  context = {'areas': areas, 'is_admin': is_admin, 'section': 'areas'}

  # Apply filters from request if any
  print("area filters:", filters)
  # type, owner, title
  if filters:
    if 'type' in filters and filters['type'] != 'all':
      areas = areas.filter(type=filters['type'])
      print('type filter:', areas)

    if 'owner' in filters:
      print('filtering owners')
      staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
      if filters['owner'] == 'staff':
        print('staff only')
        areas = areas.filter(owner__groups__in=staff_groups)
      elif filters['owner'] == 'contributors':
        print('exclude staff;')
        areas = areas.exclude(owner__groups__in=staff_groups)
      print('owner filter:', areas)

    if 'title' in filters and filters['title']:
      search_term = filters['title']
      areas = areas.filter(Q(title__icontains=search_term) | Q(description__icontains=search_term))
      print('title filter:', areas)

    context = {
        'areas': areas,
        'is_admin': is_admin,
        'section': 'areas',
        'filtered': True,
        'filters': {
            'type': request.GET.get('type', ''),
            'owner': request.GET.get('owner', ''),
            'title': request.GET.get('title', '')
        }
    }
  return render(request, 'lists/area_list.html', context)

def dataset_list(request, sort='', order=''):
  filters = request.GET
  print("dataset_list() GET:", request.GET)
  print('dataset_list() sort, order', sort, order)

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  datasets = get_objects_for_user(Dataset, request.user, {'owner': request.user}, is_admin)
  text_fields = ['title', 'label', 'status', 'owner']

  # Sort based on the parameters
  if sort == 'last_modified':
    if order == 'desc':
      datasets = datasets.order_by('-create_date')
    else:
      datasets = datasets.order_by('create_date')
  elif sort and order:
    if sort == 'owner':
      sort = 'owner__username'
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
  context = {'datasets': datasets, 'is_admin': is_admin, 'section': 'datasets'}


  print("Filters received:", filters)
  # ds_status, owner, title
  if filters:
    if 'ds_status' in filters and filters['ds_status'] != 'all':
      if filters['ds_status'] == 'published':
        datasets = datasets.filter(public=True)
      else:
        datasets = datasets.filter(ds_status=filters['ds_status'])

    if 'owner' in filters:
      staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
      if filters['owner'] == 'staff':
        datasets = datasets.filter(owner__groups__in=staff_groups)
      elif filters['owner'] == 'contributors':
        datasets = datasets.exclude(owner__groups__in=staff_groups)

    if 'title' in filters and filters['title']:
      # datasets = datasets.filter(title__icontains=filters['title'])
      search_term = filters['title']
      datasets = datasets.filter(Q(title__icontains=search_term) | Q(owner__username__icontains=search_term))
      print('title filter:', datasets)

    context = {
        'datasets': datasets,
        'is_admin': is_admin,
        'section': 'datasets',
        'filtered': True,
        'filters': {
            'ds_status': request.GET.get('ds_status', ''),
            'owner': request.GET.get('owner', ''),
            'title': request.GET.get('title', '')
        }
    }

  return render(request, 'lists/dataset_list.html', context)

def collection_list(request, sort='', order=''):
  filters = request.GET
  print("collection_list() GET (filters):", request.GET)
  print('collection_list() sort, order', sort, order)

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  text_fields = ['title', 'type', 'status', 'owner']

  collections = Collection.objects.all()
  # collections = collections.annotate(recent_log_timestamp=Max('log__timestamp')).order_by('recent_log_timestamp')
  #
  # collections = collections.annotate(
  #   count=Case(
  #     When(collection_class='place', then=Count('annos')),
  #     # When(collection_class='dataset', then=Count('datasets__places')),
  #     default=0
  #   )
  # )

  # Sort based on the parameters
  if sort == 'create_date':
    if order == 'desc':
      collections = collections.order_by('-create_date')
    else:
      collections = collections.order_by('create_date')
  elif sort == 'count':
    if order == 'desc':
      collections = collections.order_by('-count')
    else:
      collections = collections.order_by('count')
  elif sort and order:
    if sort == 'owner':
      sort = 'owner__username'
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
  context = {'collections': collections, 'is_admin': is_admin, 'section': 'collections'}


  print("Filters received:", filters)
  # status, collection_class, owner, title
  if filters:
    if 'status' in filters and filters['status'] != 'all':
      collections = collections.filter(status=filters['status'])
      print('status filter:', collections)

    if 'class' in filters and filters['class'] != 'all':
      collections = collections.filter(collection_class=filters['class'])
      print('class filter:', collections)

    if 'owner' in filters:
      staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
      if filters['owner'] == 'staff':
        collections = collections.filter(owner__groups__in=staff_groups)
      elif filters['owner'] == 'contributors':
        collections = collections.exclude(owner__groups__in=staff_groups)
      print('owner filter:', collections)

    if 'title' in filters and filters['title']:
      # collections = collections.filter(title__icontains=filters['title'])
      search_term = filters['title']
      collections = collections.filter(Q(title__icontains=search_term) | Q(owner__username__icontains=search_term))
      print('title filter:', collections)

    context = {
        'collections': collections,
        'is_admin': is_admin,
        'section': 'collections',
        'filtered': True,
        'filters': {
            'status': request.GET.get('status', ''),
            'class': request.GET.get('class', ''),
            'owner': request.GET.get('owner', ''),
            'title': request.GET.get('title', '')
        }
    }

  return render(request, 'lists/collection_list.html', context)

def group_list(request, sort='', order=''):
  filters = request.GET
  print("group_list() GET (filters):", request.GET)
  print('group_list() sort, order', sort, order)

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  text_fields = ['title', 'category', 'owner']

  groups = CollectionGroup.objects.all()

  if sort and order:
    if sort == 'owner':
      sort = 'owner__username'
    if sort in text_fields:
        # Apply Lower function for text fields
        if order == 'desc':
            groups = groups.order_by(Lower(sort).desc())
        else:
            groups = groups.order_by(Lower(sort))
    else:
        sort_param = f'-{sort}' if order == 'desc' else sort
        groups = groups.order_by(sort_param)
  context = {'groups': groups, 'is_admin': is_admin, 'section': 'groups'}

  print("group filters:", filters)
  # type, owner, title
  if filters:
    if 'type' in filters and filters['type'] != 'all':
      groups = groups.filter(type=filters['type'])
      print('type filter:', groups)

    if 'owner' in filters:
      staff_groups = Group.objects.filter(name__in=['whg_admins', 'whg_staff'])
      if filters['owner'] == 'staff':
        groups = groups.filter(owner__groups__in=staff_groups)
      elif filters['owner'] == 'users':
        groups = groups.exclude(owner__groups__in=staff_groups)
      print('owner filter:', groups)

    if 'title' in filters and filters['title']:
      groups = groups.filter(title__icontains=filters['title'])
      print('title filter:', groups)

    context = {
        'groups': groups,
        'is_admin': is_admin,
        'section': 'groups',
        'filtered': True,
        'filters': {
            'type': request.GET.get('class', ''),
            'owner': request.GET.get('owner', ''),
            'title': request.GET.get('title', '')
        }
    }

  return render(request, 'lists/group_list.html', context)


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
  print('dashboard_admin() request.GET', request.GET)
  user = request.user
  is_admin = user.groups.filter(name='whg_admins').exists()
  print(f'Is Admin: {is_admin}')
  is_leader = user.groups.filter(name='group_leaders').exists()
  django_groups = [group.name for group in user.groups.all()]


  user_datasets_count = Dataset.objects.filter(owner=user.id).count()
  user_collections_count = Collection.objects.filter(owner=user).count()

  # section = request.GET.get('section')
  section = request.GET.get('section', 'datasets')

  #
  datasets = get_objects_for_user(Dataset, request.user, {}, is_admin)
  datasets = datasets.order_by('create_date')

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
  return render(request, 'main/dashboard_admin.html', context)

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
  user_resources_count = Resource.objects.filter(owner=user).count()
  user_downloads_count = DownloadFile.objects.filter(user=user).count()

  section = request.GET.get('section')

  datasets = get_objects_for_user(Dataset, request.user, {'owner': user}, False)
  collections = get_objects_for_user(Collection, request.user, {'owner': user}, False)
  areas = get_objects_for_user(Area, request.user, {'owner': user}, False)
  resources = get_objects_for_user(Resource, request.user, {'owner': user}, False)
  downloads = get_objects_for_user(DownloadFile, request.user, {'user': user}, False)
  groups_member = CollectionGroup.objects.filter(members__user=user)
  groups_led = CollectionGroup.objects.filter(owner=user)

  context = {
    'datasets': datasets,
    'collections': collections,
    'areas': areas,
    'resources': resources,
    'downloads': downloads,
    'has_datasets': datasets.count() > 0,
    'has_collections': collections.count() > 0,
    'has_areas': user_areas_count > 0,
    'has_resources': user_resources_count > 0,
    'has_downloads': user_downloads_count > 0,
    'section': section,
    'django_groups': django_groups,
    'groups_member': groups_member,
    'groups_led': groups_led,
    'is_admin': is_admin,
    'is_leader': is_leader,
    'box_titles': ['Datasets', 'Place Collections', 'Dataset Collections', 'Study Areas', 'Groups'],

  }
  return render(request, 'main/dashboard_user.html', context)

# @csrf_exempt
# def home_modal(request):
#   page = request.POST['page']
#   context = {'v1': 'hello there'}
#   url = 'home/' + page + '.html'
#   print('home_modal() url:', url)
#   return render(request, url, context)

# main/views.py
from django.shortcuts import render

def trigger_500_error(request):
    # This will simulate a server error
    raise Exception("Simulated server error")

def server_error_view(request):
    import traceback

    try:    
        print('Formatting message for Slack...')

        # Capture request details
        path = request.get_full_path().lstrip('/')
        url = f"{settings.URL_FRONT}{path}"
        method = request.method
        headers = dict(request.headers)
        headers_pretty = json.dumps(headers, indent=2)
        body = request.body.decode('utf-8', errors='replace')
        body_formatted = f"```{body}```" if body else 'None'
        
        # Capture authenticated user details
        if request.user and request.user.is_authenticated:
            authenticated_user = f'{request.user.username} ({request.user.email})'
        else:
            authenticated_user = 'None'

        # Capture exception details
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exc_type = exc_type.__name__ if exc_type else 'N/A'
        exc_message = str(exc_value) if exc_value else 'N/A'
        tb = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)) if exc_traceback else 'N/A'

        # Prepare the Slack message
        message = (
            f"*{exc_type.upper()}: {exc_message.upper()}*\n"
            f"*URL:* {url}\n"
            f"*Method:* {method}\n"
            f"*Authenticated User:* {authenticated_user}\n"
            f"*Headers:* ```{headers_pretty}```\n"
            f"*Body:* {body_formatted}\n"
            f"*Traceback:* ```{tb}```"
            f"----------------------------------------"
        )

        payload = {
            "text": message
        }

        # Send the message to Slack
        response = requests.post(settings.SLACK_ERROR_WEBHOOK, json=payload)

        if response.status_code == 200:
            # Log the error or handle it accordingly
            print(f"Message sent to Slack.")
        else:
            print(f"Failed to send message to Slack: {response.status_code}, {response.text}")

    except Exception as e:
        # Handle exceptions that occur while sending the message to Slack (avoid infinite loop!)
        print(f"Error sending message to Slack: {e}")       

    # Return a user-friendly error page
    context = { # Rendering of this message is not currently implemented
        'error_message': 'An unexpected error occurred. Our team has been notified and is looking into the issue. Please try again later.'
    }
    try:
        return render(request, "main/500.html", context, status=500)
    except Exception as e:
        # In case rendering the error page fails, return a plain HTTP response
        return HttpResponseServerError('An unexpected error occurred and we were unable to handle it properly.')

# def server_error_view(request, exception=None):
#   import traceback
#   # Capture request details
#   url = request.build_absolute_uri()
#   method = request.method
#   headers = dict(request.headers)
#   body = request.body.decode('utf-8', errors='replace')
#
#   # Capture exception details
#   exc_type = type(exception).__name__ if exception else 'N/A'
#   exc_message = str(exception) if exception else 'N/A'
#   tb = traceback.format_exc()
#
#   # Send the email with details
#   # new_emailer(
#   #   email_type='500_error',
#   #   subject='Server error',
#   #   from_email=settings.DEFAULT_FROM_EMAIL,
#   #   to_email=settings.EMAIL_TO_ADMINS,  # a list in settings
#   #   username=request.user.username if request.user.is_authenticated else 'Anonymous',
#   #   url=url,
#   #   method=method,
#   #   headers=headers,
#   #   body=body,
#   #   exc_type=exc_type,
#   #   exc_message=exc_message,
#   #   traceback=tb,
#   # )
#
#   return render(request, "main/500.html", {'error': 'fubar'}, status=500)


# def server_error_view(request, exception=None):
#     print('500 error request', request.GET.__dict__)
#     new_emailer(
#       email_type='500_error',
#       subject='Server error',
#       from_email=settings.DEFAULT_FROM_EMAIL,
#       to_email=settings.EMAIL_TO_ADMINS,
#       username=request.user.username,
#     )
#     return render(request, "main/500.html", {'error':'fubar'})

def custom_404(request, exception):
  print('404 error request', request.GET.__dict__)
  return render(request, 'main/404.html', {}, status=404)

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


def volunteer_view(request):
  if request.method == 'POST':
    form = VolunteerForm(request.POST)
    if form.is_valid():
        # Extract the data from the form
        name = form.cleaned_data['name']
        email = form.cleaned_data['from_email']
        message = form.cleaned_data['message']
        dataset_id = form.cleaned_data.get('dataset_id')
        dataset = Dataset.objects.get(id=dataset_id)
        
        # Send the email
        try:
            new_emailer(
                email_type='volunteer_offer_owner',
                subject='WHG Volunteer to Review',
                from_email=email,
                to_email=[dataset_owner_email],  # Replace with the dataset owner's email
                # cc=['admin1@example.com', 'admin2@example.com'],  # Uncomment and replace with the site admins' emails if needed
                name=name,
                message=message,
                dataset_title=dataset.title,
                dataset_id=dataset.id
            )
        except Exception as e:
            print('Error occurred while sending volunteer offer email to owner', e)
            logger.exception("Error occurred while sending volunteer offer email to owner")
        
        try:
            slack_message = (
                f"*Subject:* WHG Volunteer to Review\n"
                f"*From:* {name} (email: {email})\n"
                f"*Message:* {message}\n"
                f"*Dataset Title:* {dataset.title}\n"
                f"*Dataset ID:* {dataset.id}\n"
                f"----------------------------------------"
            )
            response = requests.post(settings.SLACK_NOTIFICATION_WEBHOOK, json={"text": slack_message})
            if response.status_code == 200:
                print("Message sent to Slack.")
            else:
                print(f"Failed to send message to Slack: {response.status_code}, {response.text}")
        except Exception as e:
            print('Error occurred while sending Slack notification for volunteer offer', e)
            logger.exception("Error occurred while sending Slack notification for volunteer offer")

        return redirect('/success?return=' + request.GET.get('from', '/'))
  else:
    form = VolunteerForm()

  return render(request, 'volunteer.html', {'form': form})

# # contact form used throughout
# def contact_view(request):
#   sending_url = request.GET.get('from')
#   initial_subject = request.GET.get('subject', None)
#   dataset_id = request.GET.get('dataset_id', None)
#   dataset = Dataset.objects.get(id=dataset_id) if dataset_id else None
#   is_volunteer = False
#   if sending_url == '/datasets/volunteer_requests/' and dataset:
#     is_volunteer = True
#   print('contact_view() sending_url:', sending_url)
#   print('dataset:', dataset.title if dataset else None)
#   if request.method == 'GET':
#     if is_volunteer:
#       user_email = request.user.email
#       username = request.user.username
#       name = request.user.first_name  # or another field that stores the user's name
#       owner_greeting = dataset.owner.name if dataset.owner.name else dataset.owner.username
#       # Send the volunteer offer emails here
#       try:
#         # message to dataset owner, cc editors
#         new_emailer(
#           email_type='volunteer_offer_owner',
#           subject=f'WHG volunteer offer',
#           from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt to admins
#           to_email=[dataset.owner.email],  # to ds owner
#           reply_to=[user_email],  # owner replies to user
#           owner_name=dataset.owner.name,  # owner's name
#           name=name,  # user's name
#           greeting_name=name if name else username,
#           username=username,  # user's username
#           user_subject=initial_subject,  # user-submitted subject
#           user_email=user_email,  # user's email
#           dataset_title=dataset.title,
#           dataset_id=dataset.id,
#         )
#         # 'received' reply to sender
#         new_emailer(
#           email_type='volunteer_offer_user',
#           subject="WHG volunteering offer received",  # got it
#           from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt
#           to_email=[user_email],  # to sender
#           reply_to=[settings.DEFAULT_FROM_EDITORIAL],  # reply-to editorial
#           cc=[settings.DEFAULT_FROM_EDITORIAL],  # cc editorial
#           name=name,  # user's name
#           owner_greeting=owner_greeting,
#           greeting_name=name if name else username,
#           user_subject=initial_subject,  # user-submitted subject
#           dataset_title=dataset.title,
#         )
#         messages.success(request, f"Thank you! Your offer to volunteering was forwarded to the dataset owner, ({owner_greeting}).")
#       except BadHeaderError:
#         return HttpResponse('Invalid header found.')
#       return redirect('datasets:volunteer-requests')
#
#     initial_data = {}
#     if initial_subject:
#       initial_data['subject'] = initial_subject
#     if request.user.is_authenticated:
#       initial_data['from_email'] = request.user.email
#     form = ContactForm(initial=initial_data)
#   else:
#     print('contact_view() request.POST', request.POST)
#     # print('contact_view() sending_url', sending_url)
#     form = ContactForm(request.POST)
#     # print("POST request. Form: ", form)
#     if form.is_valid():
#       name = form.cleaned_data['name']
#       username = form.cleaned_data.get('username', None)
#       user_subject = form.cleaned_data['subject']
#       user_email = form.cleaned_data['from_email']
#       user_message = form.cleaned_data['message']
#       if not is_volunteer: # standard contact messages
#         try:
#           # form message to admins
#           print('EMAIL_TO_ADMINS', settings.EMAIL_TO_ADMINS)
#           new_emailer(
#             email_type='contact_form',
#             subject=user_subject, # may be supplied in request.GET
#             from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt to admins
#             to_email=settings.EMAIL_TO_ADMINS,  # to editor
#             reply_to=[user_email],  # reply-to sender
#             name=name,  # user's name
#             username=username,  # user's username
#             user_subject=user_subject,  # user-submitted subject
#             user_email=user_email,  # user's email
#             user_message=user_message,  # user-submitted message
#           )
#           # 'received' reply to sender
#           new_emailer(
#             email_type='contact_reply',
#             subject="Message to WHG received",  # got it
#             from_email=settings.DEFAULT_FROM_EMAIL,  # whg@pitt
#             to_email=[user_email],  # to sender
#             reply_to=[settings.DEFAULT_FROM_EDITORIAL],  # reply-to editorial
#             name=name,  # user's name
#             greeting_name=name if name else username,
#             user_subject=user_subject,  # user-submitted subject
#           )
#         except BadHeaderError:
#           return HttpResponse('Invalid header found.')
#
#       return redirect('/success?return=' + sending_url if sending_url else '/')
#     else:
#       print('Form errors from contact_view():', form.errors)
#
#   return render(request, "main/contact.html", {'form': form,
#                                                'user': request.user,
#                                                'is_volunteer': is_volunteer or False,
#                                                'dataset': dataset})

def contact_modal_view(request):
    
    if request.method == 'GET':
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['from_email'] = request.user.email
            initial_data['name'] = request.user.username
            initial_data['subject'] = request.GET['subject'] if 'subject' in request.GET else None
        form = ContactForm(initial=initial_data)
    else:
        print("Contact form received.")
        form = ContactForm(request.POST)
        if form.is_valid():
            print("Contact form validated.")
            name = form.cleaned_data['name']
            username = form.cleaned_data.get('username', None)
            user_subject = form.cleaned_data['subject']
            user_email = form.cleaned_data['from_email']
            user_message = form.cleaned_data['message']
            page_url = request.POST.get('page_url', 'No page URL provided')
            
            # URL-encode the subject and body for the mailto link
            encoded_subject = urllib.parse.quote(user_subject)
            encoded_body = urllib.parse.quote(
                f"\n\n\nOriginal message:\nSent on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{user_message}"
            )
            mailto_link = f"mailto:{user_email}?subject={encoded_subject}&body={encoded_body}"
            
            try:
                
                slack_message = (
                    f"*Subject:* {user_subject}\n"
                    f"*From:* {name} (username: {username or '(none)'})\n"
                    f"*Email Address:* <{mailto_link}|{user_email}>\n"
                    f"*Message:* ```{user_message}```\n"
                    f"*Page URL:* {'Home Page' if page_url == '/' else page_url}\n"
                    f"----------------------------------------"
                )
                response = requests.post(settings.SLACK_CONTACT_WEBHOOK, json={"text": slack_message})
                if response.status_code == 200:
                    print(f"Message sent to Slack.")
                else:
                    print(f"Failed to send message to Slack: {response.status_code}, {response.text}")
                
                # # reply to user
                # new_emailer(
                #     email_type='contact_reply',
                #     subject="Message to WHG received",
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     to_email=[user_email],
                #     reply_to=[settings.DEFAULT_FROM_EDITORIAL],
                #     name=name,
                #     greeting_name=name if name else username,
                #     user_subject=user_subject,
                # )
                
                messages.success(request, "Your message has been sent successfully.")
                print("Contact form processed.")
                return JsonResponse({'success': True})
            
            except BadHeaderError:
                return HttpResponse('Invalid header found.')

            except Exception as e:
                logger.error("An error occurred while processing the contact form: %s", e)
                messages.error(request, "There was an error sending your message. Please try again later.")
                return JsonResponse({'success': False, 'error': str(e)})
        else:
            print('Form errors:', form.errors)
            # Form is not valid, render the form again with errors
            return render(request, 'main/contact_modal.html', {'form': form})

    context = {'form': form}
    return render(request, 'main/contact_modal.html', context)

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

@login_required
@require_POST
def handle_comment(request):
    try:
        comment_text = escape(request.POST.get('commentText'))
        tag = request.POST.get('tag')
        place_id = request.POST.get('placeId')
        delete_id = request.POST.get('deleteId')

        if delete_id:
            # Check that comment's creator is the current request.user
            get_object_or_404(Comment, id=delete_id, user=request.user).delete()

            return JsonResponse({'success': True, 'message': f'Comment #{delete_id} deleted successfully'})

        else:

            place = get_object_or_404(Place, id=place_id)

            comment = Comment.objects.create(user=request.user, note=comment_text, tag=tag, place_id=place)

            comment_data = {
                'id': comment.id,
                'user': comment.user.id,
                'note': comment.note,
                'tag': comment.tag,
                'place_id': comment.place_id.id,
                'created': comment.created.strftime('%Y-%m-%d %H:%M:%S')
            }

            return JsonResponse({'success': True, 'message': f'Comment #{comment.id} created successfully', 'comment': comment_data})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
