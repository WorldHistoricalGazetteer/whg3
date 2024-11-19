# areas.views (study areas)
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (CreateView, UpdateView, DeleteView)

from .forms import AreaModelForm
from .models import Area
from utils.regions_countries import get_regions_countries

class AreaFormMixin:
    form_class = AreaModelForm
    template_name = 'areas/area_create.html'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Area, id=id_)

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            success_url = f"{next_url}?userarea={self.object.id}"
        else:
            success_url = reverse('dashboard')
        return success_url

    def form_invalid(self, form):
        return super().form_invalid(form)

    def form_valid(self, form):
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dropdown_data'] = get_regions_countries()
        return context

class AreaCreateView(AreaFormMixin, CreateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        return context

class AreaUpdateView(AreaFormMixin, UpdateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'update'
        return context

class AreaDeleteView(DeleteView):
    template_name = 'areas/area_delete.html'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Area, id=id_)

    def delete(self, request, *args, **kwargs):
        self.get_object().delete()
        return self.get_success_url()

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            success_url = f"{next_url}"
        else:
            success_url = reverse('dashboard')
        return success_url
