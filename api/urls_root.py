# whg/api/root_urls.py

from django.urls import path

from .preview import PreviewView
from .reconcile import ReconciliationView, SuggestEntityView, ExtendProposeView, SuggestPropertyView, \
    DummyView

urlpatterns = [
    path("reconcile", ReconciliationView.as_view(), name="reconcile"),
    path('reconcile/properties', ExtendProposeView.as_view(), name='extend-propose'),
    path("suggest/entity", SuggestEntityView.as_view(), name="suggest_entity"),
    path("suggest/property", SuggestPropertyView.as_view(), name="suggest_property"),
    path("preview", PreviewView.as_view(), name="preview"),
    # Dummy endpoint for OpenRefine's legacy search calls
    path('search/', DummyView.as_view(), name='dummy_search'),
]
