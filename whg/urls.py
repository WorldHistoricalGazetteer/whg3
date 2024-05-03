from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path, include, get_resolver
from django.views.generic.base import TemplateView

from accounts.views import profile_edit
from datasets.views import PublicListsView #, DataListsView
from main import views
from resources.views import TeachingPortalView
from utils.tasks import downloader

# For CDNfallbacks
from django.views.static import serve
from django.http import HttpResponseForbidden
from pathlib import Path

def serve_cdnfallbacks(request, path):
    host = request.headers.get('Host', '')
    print(host)
    referer = request.META.get('HTTP_REFERER')
    if 'whgazetteer.org' in host or 'localhost' in host:
        return serve(request, path, document_root=Path(settings.BASE_DIR) / 'CDNfallbacks')
    else:
        return HttpResponseForbidden(f"Access forbidden: {referer}")

#handler404 = 'datasets.views.handler404',
handler500 = 'main.views.custom_error_view'

urlpatterns = [
    # home page
    # path('', views.splash, name='splash'),
    path('', views.Home30a.as_view(), name="home"),
    path('home/<str:version>/', views.Home30a.as_view(), name='home-version'),


    # apps
    path('areas/', include('areas.urls')),
    path('collections/', include('collection.urls')),
    path('datasets/', include('datasets.urls')),
    path('elastic/', include('elastic.urls')),
    path('main/', include('main.urls')), # utility urls/views
    path('places/', include('places.urls')),
    path('resources/', include('resources.urls')),
    path('search/', include('search.urls')),

    path('guides/', include('main.urls_guides')),
    path('teaching/', TeachingPortalView.as_view(), name="teaching"),

    path('public_data/', PublicListsView.as_view(), name='public-lists'),

    # profile and settings
    path('profile/', profile_edit, name="profile-edit"),

    path('dashboard/', views.dashboard_redirect, name="dashboard"),  # redirect to user or admin
    path('dashboard_user/', views.dashboard_user_view, name="dashboard-user"),
    path('dashboard_admin/', views.dashboard_admin_view, name="dashboard-admin"),

    # static content
    path('about/', TemplateView.as_view(template_name="main/about.html"), name="about"),
    # path('builder/', TemplateView.as_view(template_name="main/builder_start.html"), name="gazetteer-builder"),
    # path('builder_single/', TemplateView.as_view(template_name="main/builder_single.html"), name="builder-single"),
    # path('builder_multiple/', TemplateView.as_view(template_name="main/builder_multiple.html"), name="builder-multiple"),
    path('contributing/', TemplateView.as_view(template_name="main/contributing.html"), name="contributing"),

    path('credits/', TemplateView.as_view(template_name="main/credits.html"), name="credits"),
    path('licensing/', TemplateView.as_view(template_name="main/licensing.html"), name="licensing"),
    path('system/', TemplateView.as_view(template_name="main/system.html"), name="system"),

    path('people/', TemplateView.as_view(template_name="main/people.html"), name="people"),
    path('partners/', TemplateView.as_view(template_name="main/partners.html"), name="partners"),
    path('publications/', TemplateView.as_view(template_name="main/publications.html"), name="publications"),

    path('usingapi/', TemplateView.as_view(template_name="main/usingapi.html"), name="usingapi"),
    path('api/', TemplateView.as_view(template_name="main/api.html"), name="api"),
    path('downloads/', TemplateView.as_view(template_name="main/downloads.html"), name="downloads"),
    path('documentation/', TemplateView.as_view(template_name="main/documentation.html"), name="documentation"),

    # more static content - 2024-01
    # path('build/', TemplateView.as_view(template_name="home/build_new.html"), name="build"),
    # path('builder/', TemplateView.as_view(template_name="home/builder.html"), name="builder"),
    path('workbench/', TemplateView.as_view(template_name="home/workbench_template.html"), name="workbench"),
    # path('workbench/', TemplateView.as_view(template_name="home/workbench.html"), name="workbench"),
    path('pipeline/', TemplateView.as_view(template_name="home/pipeline.html"), name="pipeline"),
    
    # yet more static content - 2024-02
    path('main_regions/', TemplateView.as_view(template_name="main/regions.html"), name="main-regions"),
    path('journeys_routes/', TemplateView.as_view(template_name="main/journeys_routes.html"), name="journeys-routes"),

    path('modal_home/', views.home_modal, name="modal-home"),

    path('announcement/create/', views.AnnouncementCreateView.as_view(), name='announcement-create'),
    path('announcement_delete/<int:pk>/', views.AnnouncementDeleteView.as_view(), name='announcement-delete'),
    path('announcement/update/<int:pk>/', views.AnnouncementUpdateView.as_view(), name='announcement-update'),
    path('announcements/', views.AnnouncementListView.as_view(), name='announcements-list'),

    path('comment/', views.create_comment, name='comment-create'),
    path('contact/', views.contact_view, name='contact'),
    path('success/', views.contactSuccessView, name='success'),
    path('status/', views.statusView, name='status'),
    path('create_link/', views.create_link, name="create-link"),

    # backend stuff
    path('api/', include('api.urls')),
    path('remote/', include('remote.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('captcha/', include('captcha.urls')),
    # for celery tasks
    # initiate downloads of augmented datasets via celery task (called from ajax)
    path('dlcelery/', downloader, name='dl_celery'),
    path('task_progress/<str:taskid>/', views.get_task_progress, name='task-progress'),

    # Serve the CDNfallbacks folder with host check
    re_path(r'^CDNfallbacks/(?P<path>.*)$', serve_cdnfallbacks),

] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)


# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns += [
#         path('__debug__/', include(debug_toolbar.urls)),
#     ]
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
