# api/serializers_api.py

from rest_framework import serializers

from api.serializers import PlaceNameSerializer, PlaceTypeSerializer, PlaceGeomSerializer, PlaceLinkSerializer, \
    PlaceRelatedSerializer, PlaceWhenSerializer, PlaceDescriptionSerializer, PlaceDepictionSerializer
from areas.models import Area
from collection.models import Collection
from datasets.models import Dataset
from places.models import Place


class AreaFeatureSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for an Area, intended for feature (machine-readable) views.
    Expand with geometry, metadata, etc. as needed.
    """

    class Meta:
        model = Area
        fields = [
            "id",
            "name",
            "description",  # assuming your model has this
            "geometry",  # GeoJSONField or similar
        ]


class AreaPreviewSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for an Area preview snippet.
    Intended for reconciliation preview (HTML/JSON summary).
    """

    class Meta:
        model = Area
        fields = [
            "id",
            "title",
            "description",
            "created",
            "ccodes",
        ]


class CollectionFeatureSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for a Collection, intended for feature (machine-readable) views.
    Can later embed datasets or places if required.
    """

    class Meta:
        model = Collection
        fields = [
            "id",
            "title",
            "collection_class",
            "description",
            "create_date",
        ]


class CollectionPreviewSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for a Collection preview snippet.
    Intended for reconciliation preview (HTML/JSON summary).
    """
    datasets = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="title"
    )

    class Meta:
        model = Collection
        fields = [
            "id",
            "title",
            "creator",
            "collection_class",
            "datasets",
            "description",
            "create_date",
        ]


class DatasetFeatureSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = ["id", "title", "description", "download_url"]

    def get_download_url(self, obj):
        return self.context["request"].build_absolute_uri(f"/dataset/download/{obj.id}/")


class DatasetPreviewSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for reconciliation preview snippets.
    Provides title, description, and summary metadata.
    """

    class Meta:
        model = Dataset
        fields = [
            "id",
            "title",
            "creator",
            "description",
            "numrows",
            "create_date",
        ]


class PlacePreviewSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for reconciliation preview snippets.
    Provides name, description, and key locational fields.
    """
    names = PlaceNameSerializer(many=True, read_only=True)
    types = PlaceTypeSerializer(many=True, read_only=True)
    whens = PlaceWhenSerializer(many=True, read_only=True)
    class Meta:
        model = Place
        fields = ["id", "title", "names", "types", "ccodes", "fclasses", "whens", "dataset"]


class PlaceFeatureSerializer(serializers.ModelSerializer):
    """
    Full serializer for place feature representations.
    Includes identifiers, dataset metadata, names, types,
    geometries, temporal extents, relationships, and media.
    Suitable for machine-readable exchange.
    """

    dataset = serializers.ReadOnlyField(source="dataset.title")
    dataset_id = serializers.ReadOnlyField(source="dataset.id")

    names = PlaceNameSerializer(many=True, read_only=True)
    types = PlaceTypeSerializer(many=True, read_only=True)
    geoms = PlaceGeomSerializer(many=True, read_only=True)
    extent = serializers.ReadOnlyField()
    links = PlaceLinkSerializer(many=True, read_only=True)
    related = PlaceRelatedSerializer(many=True, read_only=True)
    whens = PlaceWhenSerializer(many=True, read_only=True)
    descriptions = PlaceDescriptionSerializer(many=True, read_only=True)
    depictions = PlaceDepictionSerializer(many=True, read_only=True)

    traces = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = (
            "url",
            "id",
            "title",
            "src_id",
            "dataset",
            "dataset_id",
            "ccodes",
            "fclasses",
            "names",
            "types",
            "geoms",
            "extent",
            "links",
            "related",
            "whens",
            "descriptions",
            "depictions",
            "minmax",
            "traces",
        )

    def get_traces(self, obj):
        """Stub for traces until implemented."""
        return None
