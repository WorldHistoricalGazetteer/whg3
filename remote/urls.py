from django.urls import path
from . import views

urlpatterns = [
    # Collection URLs
    path('remote/coll/', 
         views.CollectionViewSet.as_view({
             'get': 'list', 
             'post': 'create'
             }), 
         name='collection-list-create'),

    # Dataset URLs
    path('remote/ds/', 
         views.DatasetViewSet.as_view({
             'get': 'list', 
             'post': 'create'
             }), 
         name='dataset-list-create'),
    # path('remote/ds/<int:pk>/', 
    #      views.DatasetViewSet.as_view({
    #          'get': 'retrieve', 
    #          'put': 'update', 
    #          'patch': 'partial_update', 
    #          'delete': 'destroy'
    #          }), 
    #      name='dataset-detail'),
    
    # Place URLs
    path('remote/pl/', 
         views.PlaceViewSet.as_view({
             'get': 'list', 
             'post': 'create'
             }), 
         name='place-list-create'),
    # path('remote/pl/<int:pk>/', 
    #      views.PlaceViewSet.as_view({
    #          'get': 'retrieve', 
    #          'put': 'update', 
    #          'patch': 'partial_update', 
    #          'delete': 'destroy'
    #          }), 
    #      name='place-detail'),
    
    # Type URLs
    # NOT IMPLEMENTED
]
