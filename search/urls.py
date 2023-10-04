# search/urls.py
from django.urls import path #, include

from search.views import (
  SearchView, SearchPageView, FeatureContextView, TraceGeomView,
  SearchDatabaseView, CollectionGeomView, SearchPageViewNew
)

#app_name = "search"

urlpatterns = [
  path('', SearchPageView.as_view(), name='search-page'),
  path('new/', SearchPageViewNew.as_view(), name='search-page-new'),
  path('index/', SearchView.as_view(), name='search'), # executes index search
  path('db/', SearchDatabaseView.as_view(), name='search-db'), # executes database search
  path('context/', FeatureContextView.as_view(), name='feature_context'), # place portal context
  path('tracegeom/', TraceGeomView.as_view(), name='trace_geom'), # trace features <- search & place portal
  path('collgeom/', CollectionGeomView.as_view(), name='collection_geom'), # collection features <- search & place portal

  path('db/', SearchDatabaseView.as_view(), name='search-db'), # executes database search
]

