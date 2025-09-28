# whg/api/root_urls.py

from django.urls import path
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer

from periods.api.reconcile import ChrononymReconciliationView, ChrononymSuggestView, ChrononymPreviewView
from .reconcile import ReconciliationView, SuggestEntityView, ExtendProposeView, SuggestPropertyView, \
    DummyView
from .views_generic import CustomSwaggerUIView, GenericFeatureView, GenericDetailView, GenericPreviewView, \
    GenericUpdateView, GenericDeleteView, GenericCreateView


@extend_schema_view(
    get=extend_schema(
        tags=["Schema"],
        responses={200: OpenApiResponse(description="OpenAPI schema for the API")},
    )
)
class SchemaAPIView(SpectacularAPIView):
    """Forces Swagger UI to display JSON in the Responses tab, even when YAML is requested."""
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer] + SpectacularAPIView.renderer_classes[1:]


SchemaRedocView = extend_schema_view(
    get=extend_schema(tags=["Schema"])
)(SpectacularRedocView)

urlpatterns = [
    # Schema and documentation endpoints
    path("api/schema/", SchemaAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", CustomSwaggerUIView.as_view(), name="swagger-ui"),
    path("api/schema/redoc/", SchemaRedocView.as_view(url_name="schema"), name="redoc"),

    ## Reconciliation API endpoints
    path("reconcile", ReconciliationView.as_view(), name="reconcile"),
    path('reconcile/properties', ExtendProposeView.as_view(), name='extend-propose'),
    path("suggest/entity", SuggestEntityView.as_view(), name="suggest_entity"),
    path("suggest/property", SuggestPropertyView.as_view(), name="suggest_property"),

    # Generic endpoints for multiple object types
    path("<str:obj_type>/<str:id>/", GenericDetailView.as_view(), name="generic-detail"),
    path("<str:obj_type>/api/<str:id>/", GenericFeatureView.as_view(), name="generic-api"),
    path("<str:obj_type>/preview/<str:id>/", GenericPreviewView.as_view(), name="generic-preview"),
    path("<str:obj_type>/update/<str:id>/", GenericUpdateView.as_view(), name="generic-replace"),
    path("<str:obj_type>/delete/<str:id>/", GenericDeleteView.as_view(), name="generic-delete"),
    path("<str:obj_type>/create/", GenericCreateView.as_view(), name="generic-create"),

    # Dummy endpoint: serves both as a placeholder and as an inert handler for OpenRefine's legacy search calls
    path('search/', DummyView.as_view(), name='dummy_search'),
]
