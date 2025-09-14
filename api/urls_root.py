# whg/api/root_urls.py

from django.urls import path
from .reconcile import ReconciliationView, SuggestView, ExtendProposeView, ExtendView

urlpatterns = [
    path("reconcile/", ReconciliationView.as_view(), name="reconcile"),
    path("suggest/", SuggestView.as_view(), name="suggest"),
    path('reconcile/extend/propose', ExtendProposeView.as_view(), name='extend-propose'),
    path('reconcile/extend/', ExtendView.as_view(), name='extend'),
]
