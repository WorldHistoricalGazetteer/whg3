from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path, include, get_resolver
from django.views.generic.base import TemplateView

from main import views
from datasets.views import PublicListsView #, DataListsView
from resources.views import TeachingPortalView

# For CDNfallbacks
from django.views.static import serve
from django.http import HttpResponseForbidden
from pathlib import Path

def serve_cdnfallbacks(request, path):
    host = request.headers.get('Host', '')
    print(host)
    if 'whgazetteer.org' in host or 'localhost' in host:
        return serve(request, path, document_root=Path(settings.BASE_DIR) / 'CDNfallbacks')
    else:
        return HttpResponseForbidden(f"Access forbidden: {referer}")

#handler404 = 'datasets.views.handler404',
handler500 = 'main.views.custom_error_view'

urlpatterns = [
    path('', views.Home30a.as_view(), name="home"),
    path('libre/', views.LibreView.as_view(), name='libre'),

    # apps
    path('search/', include('search.urls')),
    path('datasets/', include('datasets.urls')),
    path('areas/', include('areas.urls')),
    path('collections/', include('collection.urls')),
    path('places/', include('places.urls')),
    path('elastic/', include('elastic.urls')),
    path('main/', include('main.urls')), # utility urls/views
    path('tutorials/', include('main.urls_tutorials')),
    path('resources/', include('resources.urls')),

    path('public_data/', PublicListsView.as_view(), name='public-lists'),

    # redirect to correct dashboard
    path('dashboard/', views.dashboard_redirect, name="dashboard"),
    path('dashboard_user/', views.dashboard_user_view, name="dashboard-user"),
    path('dashboard_admin/', views.dashboard_admin_view, name="dashboard-admin"),
    # profile and settings
    path('profile/', views.profile_edit, name="profile-edit"),

    # static content
    path('about/', TemplateView.as_view(template_name="main/about.html"), name="about"),
    path('builder/', TemplateView.as_view(template_name="main/builder_start.html"), name="gazetteer-builder"),
    path('builder_single/', TemplateView.as_view(template_name="main/builder_single.html"), name="builder-single"),
    path('builder_multiple/', TemplateView.as_view(template_name="main/builder_multiple.html"), name="builder-multiple"),
    path('contributing/', TemplateView.as_view(template_name="main/contributing.html"), name="contributing"),
    path('credits/', TemplateView.as_view(template_name="main/credits.html"), name="credits"),
    path('licensing/', TemplateView.as_view(template_name="main/licensing.html"), name="licensing"),
    path('system/', TemplateView.as_view(template_name="main/system.html"), name="system"),
    path('usingapi/', TemplateView.as_view(template_name="main/usingapi.html"), name="usingapi"),
    path('tinymce/', include('tinymce.urls')),

    path('modal_home/', views.home_modal, name="modal-home"),

    path('comment/<int:rec_id>', views.CommentCreateView.as_view(), name='comment-create'),
    path('contact/', views.contactView, name='contact'),
    path('success/', views.contactSuccessView, name='success'),
    path('status/', views.statusView, name='status'),
    path('create_link/', views.create_link, name="create-link"),

                  # backend stuff
    path('api/', include('api.urls')),
    path('remote/', include('remote.urls')),
    # path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('captcha/', include('captcha.urls')),

    re_path(r'^celery-progress/', include('celery_progress.urls')),  # the endpoint is configurable
    
    # Serve the CDNfallbacks folder with host check
    re_path(r'^CDNfallbacks/(?P<path>.*)$', serve_cdnfallbacks),

] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
