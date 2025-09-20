# whg/api/root_urls.py

from django.urls import path

from .preview import PreviewView
from .reconcile import ReconciliationView, SuggestEntityView, ExtendProposeView, ExtendView, SuggestPropertyView, \
    DummyView

urlpatterns = [
    path("reconcile/", ReconciliationView.as_view(), name="reconcile"),
    path('reconcile/properties', ExtendProposeView.as_view(), name='extend-propose'),
    path('reconcile/extend', ExtendView.as_view(), name='extend'),
    path("suggest/entity", SuggestEntityView.as_view(), name="suggest_entity"),
    path("suggest/property", SuggestPropertyView.as_view(), name="suggest_property"),
    path("preview/", PreviewView.as_view(), name="preview"),
    # Dummy endpoint for OpenRefine's legacy search calls
    path('search/', DummyView.as_view(), name='dummy_search'),

    # Facilitate calls with token in URL path (fails for OpenRefine `reconcile/extend` calls)
    path("<str:token>/reconcile/", ReconciliationView.as_view(), name="reconcile-token"),
    path('<str:token>/reconcile/properties', ExtendProposeView.as_view(), name='extend-propose-token'),
    path('<str:token>/reconcile/extend', ExtendView.as_view(), name='extend-token'),
    path("<str:token>/suggest/entity", SuggestEntityView.as_view(), name="suggest_entity-token"),
    path("<str:token>/suggest/property", SuggestPropertyView.as_view(), name="suggest_property-token"),
    path("<str:token>/preview/", PreviewView.as_view(), name="preview-token"),
    # Dummy endpoint for OpenRefine's legacy search calls
    path('<str:token>/search/', DummyView.as_view(), name='dummy_search-token'),
]
