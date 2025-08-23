import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ExpressionWrapper, BooleanField
from django.db.models.functions import Random
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import (FormView, UpdateView, DetailView, DeleteView, TemplateView)

from collection.models import Collection
from main.models import Log
from .forms import ResourceModelForm
from .models import *

logger = logging.getLogger(__name__)


@require_GET
def teaching_json(request):
    # Main queryset
    resources_qs = (
        Resource.objects.filter(public=True)
        .annotate(
            is_featured=ExpressionWrapper(
                Q(featured__isnull=False),
                output_field=BooleanField()
            )
        )
        .order_by("-is_featured", Random())
        .prefetch_related("regions")
    )

    # Resources serialised
    resources = [
        {
            "id": r.id,
            "title": r.title,
            "type": r.type,
            "description": r.description,
            "is_featured": r.is_featured,
            "regions": [area.id for area in r.regions.all()],
        }
        for r in resources_qs
    ]

    # Unique region IDs across all resources
    region_ids = sorted({rid for r in resources for rid in r["regions"]})

    # Nominated collections
    nominated = list(
        Collection.objects.filter(
            status="nominated", collection_class="place", public=True
        )
        .order_by("title")
        .values("id", "title", "owner__name", "description")
    )

    # Area features (GeoJSON)
    qs = Area.objects.filter(
        type="predefined",
        description="UN Statistical Division Sub-Region",
        id__in=region_ids,
    ).values("id", "title", "type", "description", "geojson")

    area_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": a["id"],
                "properties": {
                    "title": a["title"],
                    "type": a["type"],
                    "description": a["description"],
                },
                "geometry": a["geojson"],
            }
            for a in qs
        ],
    }

    data = {
        "resources": resources,
        "regions": region_ids,
        "nominated": nominated,
        "total_resources": len(resources),
        "areas": area_geojson,
    }

    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


class TeachingPortalView(TemplateView):
    """
    Renders the teaching portal page with a gallery of resources.
    """
    template_name = "resources/teaching.html"


def handle_resource_file(f):
    with open('media/resources/' + f._name, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


#
# create
#
class ResourceCreateView(LoginRequiredMixin, FormView):
    form_class = ResourceModelForm
    template_name = 'resources/resource_create.html'

    def get_success_url(self):
        Log.objects.create(
            category='resource',
            logtype='create',
            user_id=self.request.user.id
        )
        return reverse('data-resources')

    #
    def get_form_kwargs(self, **kwargs):
        kwargs = super(ResourceCreateView, self).get_form_kwargs()
        return kwargs

    def form_invalid(self, form):
        logger.debug(f'form invalid, errors: {form.errors.as_data()}')
        logger.debug(f'form invalid, cleaned_data: {form.cleaned_data}')
        context = {'form': form}
        return self.render_to_response(context=context)

    def form_valid(self, form):
        context = {}
        if form.is_valid():
            form.save(commit=True)
        else:
            logger.debug(f'form not valid, errors: {form.errors.as_data()}')
            context['errors'] = form.errors
        return super().form_valid(form)

        # def form_valid(self, form):
        #   data = form.cleaned_data
        #   print('data from resource create form', data)
        #   context = {}
        #   user = self.request.user
        #   files = self.request.FILES.getlist('files')
        #   images = self.request.FILES.getlist('images')
        #   print('resources FILES[files]', files)
        #   print('resources FILES[images]', images)

        # save to media/resources
        for f in files:
            # handle_resource_file(f)
            ResourceFile.objects.create(
                file=f
            )

        for i in images:
            # handle_resource_file(i)o something with each file.
            ResourceImage.objects.create(
                file=f
            )

        form.save(commit=True)

        return redirect('/myresources')

        # create

    # def post(self, request, *args, **kwargs):
    #   print('ResourceCreate() request', request)
    #   form_class = self.get_form_class()
    #   form = self.get_form(form_class)
    #   files = request.FILES.getlist('files')
    #   images = request.FILES.getlist('images')
    #   if form.is_valid():
    #     for f in files:
    #       print('file', f)  # Do something with each file.
    #     for i in images:
    #       print('image', i)  # Do something with each file.
    #     return self.form_valid(form)
    #   else:
    #     print('invalid form', form)
    #     return self.form_invalid(form)

    # return self.form_valid(form)
    # return reverse('dashboard')
    # return self.render_to_response(context=context)

    # saves a Resource object in resources table

    # TODO: handle multiple files
    # https://docs.djangoproject.com/en/2.2/topics/http/file-uploads/
    # files = self.request.FILES.getlist('files')
    # for f in files:
    #   handle_uploaded_file(f)
    # else:
    #   print('form not valid', form.errors)
    #   context['errors'] = form.errors
    # return super().form_valid(form)

    # def get_context_data(self, *args, **kwargs):
    #   context = super(ResourceCreateView,
    #                   self).get_context_data(*args, **kwargs)
    #   user = self.request.user
    #   #_id = self.kwargs.get("id")
    #   print('ResourceCreate() user', user)

    #   context['action'] = 'create'
    #   return context


#
# update (edit)
#
class ResourceUpdateView(UpdateView):
    form_class = ResourceModelForm
    template_name = 'resources/resource_create.html'
    success_url = '/myresources'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Resource, id=id_)

    def form_valid(self, form):
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            Log.objects.create(
                # category, logtype, "timestamp", subtype, note, dataset_id, user_id
                category='resource',
                logtype='update',
                note='resource id: ' + str(obj.id) + \
                     ' by ' + self.request.user.name,
                user_id=self.request.user.id
            )
        else:
            logger.debug(f'form not valid, errors: {form.errors.as_data()}')
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super(ResourceUpdateView,
                        self).get_context_data(*args, **kwargs)
        user = self.request.user
        _id = self.kwargs.get("id")

        context['action'] = 'update'
        context['create_date'] = self.object.create_date.strftime("%Y-%m-%d")
        return context


#
# detail (public view, no edit)
#
class ResourceDetailView(DetailView):
    template_name = 'resources/resource_detail.html'

    model = Resource

    def get_context_data(self, **kwargs):
        context = super(ResourceDetailView, self).get_context_data(**kwargs)
        id_ = self.kwargs.get("pk")

        context['primary'] = ResourceFile.objects.filter(resource_id=id_, filetype='primary')
        context['supporting'] = ResourceFile.objects.filter(
            resource_id=id_, filetype='supporting')
        context['images'] = ResourceImage.objects.filter(resource_id=id_)

        return context


#
# delete (cascade)
#
class ResourceDeleteView(DeleteView):
    template_name = 'resources/resource_delete.html'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Resource, id=id_)

    def get_success_url(self):
        return reverse('myresources')
