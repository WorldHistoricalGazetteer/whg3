# validation/urls.py
from django.urls import path
from .views import get_task_status

urlpatterns = [
    path('task_status/<str:task_id>/', get_task_status, name='get_task_status'),
]
