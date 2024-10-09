# ingestion/transformers.py

from django.contrib.gis.geos import Point, Polygon


class NPRTransformer:
    """Transforms raw data into Normalised Place Records with AlternateName data."""
    transformers = {
        "Pleiades": lambda data: (
            {
                "item_id": data.get("id", ""),
                "primary_name": data.get("title", ""),
                "geometry_point": (
                    Point(float(data["reprPoint"][0]), float(data["reprPoint"][1]))
                    if isinstance(data.get("reprPoint"), list) and len(data["reprPoint"]) == 2
                    else None
                ),
                "geometry_bbox": (
                    Polygon.from_bbox(
                        [float(coord) for coord in data["bbox"]]
                    )
                    if isinstance(data.get("bbox"), list) and len(data["bbox"]) == 4
                    else None
                ),
                "feature_classes": data.get("placeTypes", []),
                # TODO: Map to GeoNames feature classes from https://pleiades.stoa.org/vocabularies/place-types
                "lpf_feature": {},  # TODO: Build LPF feature
            },
            [
                {
                    "toponym": data.get("title", ""),  # Add root title as toponym
                    "language": "",  # Language unknown for root title
                    "is_romanised": False,  # Assume title is not romanised
                    # TODO: No time data for root title, but could be inferred from other attributes?
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
        ),
        "GeoNames": lambda data: (
            {
            },
            [
            ]
        ),
        "Wikidata": lambda data: (
            {
            },
            [
            ]
        ),
        "TGN": lambda data: (
            {
            },
            [
            ]
        )
    }

    @staticmethod
    def transform(data, dataset_name):
        transformer = NPRTransformer.transformers.get(dataset_name)
        if not transformer:
            raise ValueError(f"Unknown dataset name: {dataset_name}")
        return transformer(data)
