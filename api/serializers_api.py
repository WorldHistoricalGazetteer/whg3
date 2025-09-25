# api/serializers_api.py

from pyproj import CRS, Transformer
from rest_framework import serializers
from shapely.geometry import shape
from shapely.ops import transform

from api.serializers import PlaceNameSerializer, PlaceTypeSerializer, PlaceWhenSerializer, PlaceLinkSerializer, \
    PlaceRelatedSerializer, PlaceDescriptionSerializer, PlaceDepictionSerializer
from areas.models import Area
from collection.models import Collection
from datasets.models import Dataset
from places.models import Place, PlaceGeom


class APIPlaceGeomSerializer(serializers.ModelSerializer):
    """
    PlaceGeom serializer with computed geometry helpers:
    - geojson: full geometry object from jsonb
    - geowkt: WKT string derived from jsonb
    - bbox: [minLng, minLat, maxLng, maxLat]
    - centroid: [lng, lat] in WGS84
    """

    ds = serializers.SerializerMethodField()
    geom = serializers.ReadOnlyField(source="jsonb")

    type = serializers.ReadOnlyField(source="jsonb.type")
    coordinates = serializers.ReadOnlyField(source="jsonb.coordinates")
    citation = serializers.ReadOnlyField(source="jsonb.citation")
    when = serializers.ReadOnlyField(source="jsonb.when")
    certainty = serializers.ReadOnlyField(source="jsonb.certainty")

    geojson = serializers.SerializerMethodField()
    geowkt = serializers.SerializerMethodField()
    bbox = serializers.SerializerMethodField()
    centroid = serializers.SerializerMethodField()

    def get_ds(self, obj):
        return obj.place.dataset.id

    def _shapely_geom(self, obj):
        jb = getattr(obj, "jsonb", None)
        if not jb:
            return None
        try:
            return shape(jb)
        except Exception:
            return None

    def get_geojson(self, obj):
        geojson = getattr(obj, "jsonb", None)
        if not geojson:
            return None
        return {k: v for k, v in geojson.items() if k != "geowkt"}

    def get_geowkt(self, obj):
        geojson = getattr(obj, "jsonb", None)
        if not geojson:
            return None
        return geojson.get("geowkt")

    def get_bbox(self, obj):
        g = self._shapely_geom(obj)
        if not g:
            return None
        minx, miny, maxx, maxy = g.bounds
        return [minx, miny, maxx, maxy]

    def get_centroid(self, obj):
        g = self._shapely_geom(obj)
        if not g:
            return None
        try:
            # pick a local equal-area projection centred on bbox midpoint
            minx, miny, maxx, maxy = g.bounds
            cx = (minx + maxx) / 2
            cy = (miny + maxy) / 2
            crs_wgs84 = CRS.from_epsg(4326)
            local_crs = CRS.from_proj4(
                f"+proj=aea +lat_0={cy} +lon_0={cx} "
                "+lat_1={0} +lat_2={1}".format(cy - 10, cy + 10)
            )
            transformer_to_local = Transformer.from_crs(crs_wgs84, local_crs, always_xy=True).transform
            transformer_to_wgs = Transformer.from_crs(local_crs, crs_wgs84, always_xy=True).transform

            g_local = transform(transformer_to_local, g)
            c_local = g_local.centroid
            c_wgs = transform(transformer_to_wgs, c_local)
            return [c_wgs.x, c_wgs.y]
        except Exception:
            # fallback: shapely centroid in WGS84
            c = g.centroid
            return [c.x, c.y]

    class Meta:
        model = PlaceGeom
        fields = (
            "place_id",
            "src_id",
            "type",
            "geowkt",
            "coordinates",
            "geom_src",
            "citation",
            "when",
            "title",
            "ds",
            "certainty",
            "geom",
            "geojson",
            "bbox",
            "centroid",
        )


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
    year_ranges = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = ["id", "title", "names", "types", "ccodes", "fclasses", "year_ranges", "dataset"]

    def get_year_ranges(self, obj):
        ranges = []
        for when in obj.whens.all():
            for ts in getattr(when, "timespans", []):
                start = getattr(ts.get("start"), "get", lambda _: None)("earliest") if ts.get("start") else None
                end = getattr(ts.get("end"), "get", lambda _: None)("latest") if ts.get("end") else None
                if start and end:
                    ranges.append(f"{start}-{end}")
        return ranges


class OptimizedPlaceSerializer(serializers.ModelSerializer):
    """
    Optimized serializer that only includes requested fields.
    """
    dataset = serializers.ReadOnlyField(source="dataset.title")
    dataset_id = serializers.ReadOnlyField(source="dataset.id")

    names = PlaceNameSerializer(many=True, read_only=True)
    types = PlaceTypeSerializer(many=True, read_only=True)
    geoms = APIPlaceGeomSerializer(many=True, read_only=True)
    whens = PlaceWhenSerializer(many=True, read_only=True)
    links = PlaceLinkSerializer(many=True, read_only=True)
    related = PlaceRelatedSerializer(many=True, read_only=True)
    descriptions = PlaceDescriptionSerializer(many=True, read_only=True)
    depictions = PlaceDepictionSerializer(many=True, read_only=True)

    def __init__(self, *args, **kwargs):
        # Remove fields parameter from kwargs if it exists
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    class Meta:
        model = Place
        fields = (
            "id", "title", "ccodes", "fclasses",
            "names", "types", "geoms", "extent", "whens",
            "links", "related", "descriptions", "depictions",
            "dataset", "dataset_id"
        )


class PlaceFeatureSerializer(OptimizedPlaceSerializer):
    """
    Full serializer for place feature representations.
    Includes identifiers, dataset metadata, names, types,
    geometries, temporal extents, relationships, and media.
    Suitable for machine-readable exchange.

    This is a wrapper around OptimizedPlaceSerializer that includes all fields.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass fields parameter - we want all fields for this serializer
        kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

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
