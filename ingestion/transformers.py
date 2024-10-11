# ingestion/transformers.py
import json

from django.contrib.gis.geos import GEOSGeometry

from accounts.views import logger
from areas.models import Country


class NPRTransformer:
    """Transforms raw data into Normalised Place Records with Toponyms linked by Attestations."""
    transformers = {
        "Pleiades": [
            lambda data: (
                {
                    "item_id": data.get("id", ""),
                    "primary_name": data.get("title", ""),
                    "geometry_point": (
                        [float(coord) for coord in data["reprPoint"]]
                        if isinstance(data.get("reprPoint"), list) and len(data["reprPoint"]) == 2
                        else None
                    ),
                    "geometry_bbox": (
                        [float(coord) for coord in data["bbox"]]
                        if isinstance(data.get("bbox"), list) and len(data["bbox"]) == 4
                        else None
                    ),
                    # TODO: Map to GeoNames feature classes from https://pleiades.stoa.org/vocabularies/place-types
                    "feature_classes": data.get("placeTypes", []),
                    "ccodes": isocodes(
                        data.get("features", [{'type': 'Point', 'coordinates': data.get("reprPoint", None)}]),
                        has_Decimal=True),
                    "lpf_feature": {},  # TODO: Build LPF feature
                },
                [
                    {
                        "toponym": data.get("title", ""),  # Add root title as toponym
                        "language": "",  # Language unknown for root title
                        "is_romanised": False,  # Assume title is not romanised
                        # TODO: No time data for root toponym, but could be inferred from other attributes?
                    }
                ] + [
                    {
                        "toponym": name.get("attested") or name.get("romanized", ""),
                        "language": name.get("language", ""),  # TODO: Use BCP 47 language tags
                        "is_romanised": not name.get("attested"),
                        "start": name.get("start", None),
                        "end": name.get("end", None),
                    }
                    for name in data.get("names", [])
                ]
            )
        ],
        "GeoNames": [
            lambda data: (  # Transform the primary record
                {
                    "item_id": data.get("geonameid", ""),
                    "primary_name": data.get("name", ""),
                    "geometry_point": (
                        [float(data["latitude"]), float(data["longitude"])]
                        if data.get("latitude") and data.get("longitude")
                        else None
                    ),
                    "geometry_bbox": None,
                    "feature_classes": [data.get("feature_class", "")],
                    "ccodes": (
                        data.get("cc2", "").split(",")
                        if data.get("cc2") else
                        [data.get("country_code")] or (
                            isocodes(
                                [{'type': 'Point', 'coordinates': [float(data["latitude"]), float(data["longitude"])]}]
                            ) if data.get("latitude") and data.get("longitude") else None
                        )
                    ),
                    "lpf_feature": {},
                },
                None
            ),
            lambda data: (  # Transform the alternate names
                {
                    "item_id": data.get("geonameid", ""),
                },
                [
                    {
                        "geoname_id": data.get("geonameid", ""),
                        "geoname_toponym_id": data.get("alternateNameId", ""),
                        "toponym": data.get("alternate_name", ""),
                        "language": data.get("isolanguage") or None,
                        "is_preferred": bool(data.get("isPreferredName", False)),
                        "start": data.get("from") or None,
                        "end": data.get("to") or None,
                    }
                ]
                if data.get("isolanguage") not in ["post", "iata", "icao", "faac", "abbr", "link",
                                                   "wkdt"]  # Skip non-language codes
                else None
            )
        ],
        "Wikidata": [
            lambda data: (
                {
                },
                [
                ]
            )
        ],
        "TGN": lambda data: [
            lambda data: (
                {
                },
                [
                ]
            )
        ],
        "GB1900": lambda data: [
            lambda data: (
                {
                },
                [
                ]
            )
        ],
        "fLPF": lambda data: [
            lambda data: (
                {
                },
                [
                ]
            )
        ],
    }

    @staticmethod
    def transform(data, dataset_name):
        transformer = NPRTransformer.transformers.get(dataset_name)
        if not transformer:
            raise ValueError(f"Unknown dataset name: {dataset_name}")
        return transformer(data)


def float_geometry(geometry, has_Decimal=False):
    if not has_Decimal or not geometry or 'type' not in geometry or 'coordinates' not in geometry:
        return geometry

    geom_type = geometry.get('type')
    coordinates = geometry.get('coordinates')

    # Handle various geometry types
    if geom_type in ['Point']:
        coordinates = [float(coord) for coord in coordinates]
    elif geom_type in ['LineString']:
        coordinates = [[float(coord) for coord in point] for point in coordinates]
    elif geom_type in ['Polygon']:
        coordinates = [[[float(coord) for coord in point] for point in ring] for ring in coordinates]
    elif geom_type in ['MultiPoint']:
        coordinates = [[float(coord) for coord in point] for point in coordinates]
    elif geom_type == 'MultiLineString':
        coordinates = [[[float(coord) for coord in point] for point in line] for line in coordinates]
    elif geom_type == 'MultiPolygon':
        coordinates = [[[[float(coord) for coord in point] for point in ring] for ring in polygon] for polygon in
                       coordinates]

    return {
        "type": geom_type,
        "coordinates": coordinates
    }


def isocodes(geometries, has_Decimal=False):
    # Collect ISO codes from countries intersecting with the provided geometries

    ccodes = set()
    for geom in geometries:
        geometry = geom.get('geometry', geom)

        if geometry:
            parsed_geometry = float_geometry(geometry, has_Decimal)
            logger.debug(f"Parsed geometry: {parsed_geometry}")
            geos_geometry = GEOSGeometry(json.dumps(parsed_geometry))

            # Query the Country model for intersections with the provided geometry
            qs = Country.objects.filter(mpoly__intersects=geos_geometry)
            ccodes.update([country.iso for country in qs])

    return sorted(ccodes)
