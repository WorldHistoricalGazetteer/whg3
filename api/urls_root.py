# whg/api/root_urls.py

from django.urls import path

from .preview import PreviewView
from .reconcile import ReconciliationView, SuggestView, ExtendProposeView, ExtendView, SuggestPropertyView

urlpatterns = [
    path("reconcile/", ReconciliationView.as_view(), name="reconcile"),
    path('reconcile/extend/propose', ExtendProposeView.as_view(), name='extend-propose'),
    path('reconcile/extend/', ExtendView.as_view(), name='extend'),
    path("suggest/", SuggestView.as_view(), name="suggest"),
    path("suggest/property", SuggestPropertyView.as_view(), name="suggest_property"),
    path("preview/", PreviewView.as_view(), name="preview"),
]
