from django.contrib.gis.geos import Polygon, MultiPolygon

from collection.models import Collection


def compute_collection_bbox(collection):
    if collection.collection_class == "place":
        bboxes = [
            Polygon.from_bbox(place.extent) for place in collection.places.all() if place.extent
        ]
    elif collection.collection_class == "dataset":
        bboxes = [dataset.bbox for dataset in collection.datasets.all() if dataset.bbox]
    else:
        bboxes = []

    if bboxes:
        combined_bbox = MultiPolygon(bboxes)
        return Polygon.from_bbox(combined_bbox.extent)
    else:
        return None