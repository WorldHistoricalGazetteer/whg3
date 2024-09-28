# find/urls.py

from django.urls import path
from . import views

app_name = 'find'

urlpatterns = [
    path('<str:toponym>/', views.ToponymResolveView.as_view(), name='resolve_toponym'),
]
