# whg/api/root_urls.py

from django.urls import path

from .preview import PreviewView
from .reconcile import ReconciliationView, SuggestEntityView, ExtendProposeView, ExtendView, SuggestPropertyView

urlpatterns = [
    path("<str:token>/reconcile/", ReconciliationView.as_view(), name="reconcile"),
    path('<str:token>/reconcile/extend/propose', ExtendProposeView.as_view(), name='extend-propose'),
    path('<str:token>/reconcile/extend/', ExtendView.as_view(), name='extend'),
    path("<str:token>/suggest/entity", SuggestEntityView.as_view(), name="suggest_entity"),
    path("<str:token>/suggest/property", SuggestPropertyView.as_view(), name="suggest_property"),
    path("<str:token>/preview/", PreviewView.as_view(), name="preview"),
]
