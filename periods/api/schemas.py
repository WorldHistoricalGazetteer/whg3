# periods/api/schemas.py

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import serializers


class ChrononymReconciliationRequestSerializer(serializers.Serializer):
    """Serializer for chrononym reconciliation requests"""
    queries = serializers.DictField(
        required=False,
        child=serializers.DictField(),
        help_text="Dictionary of reconciliation queries with query IDs as keys"
    )


def build_chrononym_schema_view(
        *,
        methods: dict,
        tags: list[str],
        summary: str = "",
        description: str = "",
        parameters: list[OpenApiParameter] = None,
        responses: dict = None,
        request=None,
        examples: list[OpenApiExample] = None
):
    """
    DRY wrapper for extend_schema_view for chrononym APIs.
    Follows the same pattern as the main WHG API schemas.
    """
    schema_dict = {}

    for method, config in methods.items():
        if isinstance(config, bool) and config:
            method_summary = summary
            method_description = description
            method_parameters = parameters or []
            method_responses = responses or {}
            method_request = request
            method_examples = examples or []

        elif isinstance(config, dict):
            method_summary = config.get("summary", summary)
            method_description = config.get("description", description)
            method_parameters = config.get("parameters", parameters or [])
            method_responses = config.get("responses", responses or {})
            method_request = config.get("request", request)
            method_examples = config.get("examples", examples or [])

        else:
            continue

        schema_dict[method] = extend_schema(
            tags=tags,
            summary=method_summary,
            description=method_description,
            parameters=method_parameters,
            responses=method_responses,
            request=method_request,
            examples=method_examples,
        )

    return extend_schema_view(**schema_dict)


def chrononym_reconcile_schema():
    """Schema for the Chrononym Reconciliation API endpoint"""
    return build_chrononym_schema_view(
        methods={
            "get": {
                "summary": "Get Chrononym Reconciliation Service metadata",
                "description": (
                    "Retrieve service metadata for the PeriodO Chrononyms reconciliation service. "
                    "Returns the service manifest as per Reconciliation Service API v0.2, "
                    "including URLs, default types, and preview configuration."
                ),
                "parameters": [
                    OpenApiParameter(
                        name="token",
                        required=False,
                        type=OpenApiTypes.STR,
                        location=OpenApiParameter.QUERY,
                        description="API token for authentication (optional for metadata)",
                    ),
                ],
                "responses": {
                    200: OpenApiResponse(
                        description="Service metadata including manifest, default types, and preview configuration"
                    ),
                },
            },
            "post": {
                "summary": "Submit Chrononym Reconciliation queries",
                "description": (
                    "Submit reconciliation queries to match chrononym labels against the PeriodO database. "
                    "Supports batch queries and implements the Reconciliation Service API v0.2. "
                    "Uses a three-tier matching strategy: exact matches (score 100), "
                    "prefix matches (scores 70-95), and trigram similarity matches (scores 30-85)."
                ),
                "parameters": [
                    OpenApiParameter(
                        name="token",
                        required=True,
                        type=OpenApiTypes.STR,
                        location=OpenApiParameter.QUERY,
                        description="API token for authentication",
                    ),
                    OpenApiParameter(
                        name="queries",
                        type=OpenApiTypes.STR,
                        required=False,
                        location=OpenApiParameter.QUERY,
                        description="JSON object with chrononym reconciliation queries",
                    ),
                ],
                "request": ChrononymReconciliationRequestSerializer,
                "examples": [
                    OpenApiExample(
                        name="Basic Chrononym Reconciliation",
                        description="Example of reconciling chrononym labels",
                        value={
                            "queries": {
                                "q0": {"query": "Roman Empire"},
                                "q1": {"query": "Medieval period"}
                            }
                        }
                    ),
                    OpenApiExample(
                        name="Chrononym with Type Filter",
                        description="Search with type filtering and result limits",
                        value={
                            "queries": {
                                "q0": {
                                    "query": "Bronze Age",
                                    "type": "chrononym",
                                    "limit": 5
                                }
                            }
                        }
                    ),
                ],
                "responses": {
                    200: OpenApiResponse(
                        description="Reconciliation results with candidate chrononym matches and normalized scores"
                    ),
                    400: OpenApiResponse(description="Invalid query format or missing required parameters"),
                    401: OpenApiResponse(description="Authentication failed"),
                },
            }
        },
        tags=["Chrononym Reconciliation API"],
    )


def chrononym_suggest_schema():
    """Schema for chrononym suggestion endpoint"""
    return build_chrononym_schema_view(
        methods={"get": True},
        tags=["Chrononym Reconciliation API"],
        summary="Suggest chrononyms by prefix",
        description=(
            "Returns a list of chrononym suggestions that match a given prefix. "
            "Provides fast autocomplete functionality for chrononym labels. "
            "Requires minimum 2 characters for performance reasons."
        ),
        parameters=[
            OpenApiParameter(
                name="token",
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="API token for authentication",
            ),
            OpenApiParameter(
                name="prefix",
                type=OpenApiTypes.STR,
                description="The string to match against chrononym labels (minimum 2 characters)",
                required=True,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                description="Maximum number of suggestions to return (max 20)",
                default=10,
            ),
            OpenApiParameter(
                name="callback",
                type=OpenApiTypes.STR,
                description="JSONP callback function name",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="A list of matching chrononym suggestions with language info"),
            400: OpenApiResponse(description="Invalid parameters (e.g., prefix too short)"),
            401: OpenApiResponse(description="Authentication failed"),
        },
    )


def chrononym_preview_schema():
    """Schema for chrononym preview endpoint"""
    return build_chrononym_schema_view(
        methods={"get": True},
        tags=["Chrononym Reconciliation API"],
        summary="Preview chrononym details",
        description=(
            "Returns detailed information about a specific chrononym, including "
            "related periods and language information. Can return either HTML preview "
            "for embedding or structured JSON data based on Accept header."
        ),
        parameters=[
            OpenApiParameter(
                name="chrononym_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="The chrononym ID to preview",
                required=True,
            ),
            OpenApiParameter(
                name="token",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="API token for authentication (may be required based on access settings)",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description=(
                    "Chrononym preview data. Returns HTML snippet by default, "
                    "or JSON if Accept: application/json header is sent."
                )
            ),
            404: OpenApiResponse(description="Chrononym not found"),
        },
    )


# Update the chrononym reconciliation views to use these schemas
def get_chrononym_reconcile_schema():
    """Returns the schema decorator for ChrononymReconciliationView"""
    return chrononym_reconcile_schema()


def get_chrononym_suggest_schema():
    """Returns the schema decorator for ChrononymSuggestView"""
    return chrononym_suggest_schema()


def get_chrononym_preview_schema():
    """Returns the schema decorator for ChrononymPreviewView"""
    return chrononym_preview_schema()