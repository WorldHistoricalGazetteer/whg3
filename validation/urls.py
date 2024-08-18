# validation/urls.py
from django.urls import path
from .views import process_lpf

urlpatterns = [
    path('process_lpf/', process_lpf, name='process_lpf'),
]
