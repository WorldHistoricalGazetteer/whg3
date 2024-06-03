# places.urls

from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic.base import TemplateView

from . import views
from elastic.es_utils import fetch

# place actions
app_name='places'
urlpatterns = [

    # START new urls-> views (kg 2023-10-31)
    path('portal/', views.PlacePortalView.as_view(), name='place-portal'),
    path('portal/<int:pid>/', views.PlacePortalView.as_view(), name='place-portal-pid'),
    path('portal/<str:encoded_ids>/', views.PlacePortalView.as_view(), name='place-portal-multipid'),
    path('<int:whg_id>/portal/', views.PlacePortalView.as_view(), name='place-portal-whg-id'),

    # added for sessions approach
    path('set-current-result/', views.SetCurrentResultView.as_view(), name='set-current-result'),

    # path('portal_new/', TemplateView.as_view(template_name='places/place_portal_new.html'),
    #    name='portal-new'),
    # END new urls-> views (kg 2023-10-31)

    # path('portal_new/', TemplateView.as_view(template_name='places/place_portal_new.html'), name='portal_new'),

    # single db record
    path('<int:pk>/detail', views.PlaceDetailView.as_view(), name='place-detail'),
    # single db record for modal
    path('<int:id>/modal', views.PlaceModalView.as_view(), name='place-modal'),
    
    path('defer/<int:pid>/<str:auth>/<str:last>', views.defer_review, name='defer-review'),
    
    # # page to manage indexed place relocation
    # path('relocate/', TemplateView.as_view(template_name='places/place_relocate.html'), name='place-relocate'),
    # # gets db and index records for pid
    # path('fetch/', fetch, name='place-fetch'),
    
    # ??
    path('<int:id>/full', views.PlaceFullView.as_view(), name='place-full'),

] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
