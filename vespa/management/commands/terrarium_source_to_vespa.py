import json
import os

import requests
import gzip
from io import BytesIO
from shapely.geometry import shape

from django.core.management.base import BaseCommand, CommandError
from vespa.utils import feed_file_to_vespa

geojson_url = "https://s3.amazonaws.com/elevation-tiles-prod/docs/footprints.geojson.gz"
file_path = "/app/media/data/terrarium-sources.json"

def process_geojson_to_file(geojson_url: str, file_path: str):
    """
    Fetch GeoJSON data, process it, and save documents to a file for batch upload.

    Args:
        geojson_url (str): URL of the GeoJSON file to be processed.
        file_path (str): Path to save the documents file.
    """
    # Fetch GeoJSON data from the given URL
    response = requests.get(geojson_url)
    response.raise_for_status()

    # Decompress the gzipped content and load JSON
    with gzip.GzipFile(fileobj=BytesIO(response.content)) as f:
        geojson_data = json.load(f)

    documents = []

    # Process each feature in the GeoJSON
    for i, feature in enumerate(geojson_data['features'], start=1):
        if not feature['geometry']['coordinates']:
            print(f"Skipping feature with empty coordinates: {feature}")
            continue

        # Prepare the document for Vespa
        bounds = shape(feature['geometry']).bounds
        document = {
            "id": f"terrarium-area-{i}",
            "fields": {
                "bounding_box": {"x": [bounds[0], bounds[2]], "y": [bounds[1], bounds[3]]},
                "resolution": feature['properties']['resolution'],
                "source": feature['properties']['source'],
                "geometry": json.dumps(feature['geometry'])
            }
        }
        documents.append(document)

    with open(file_path, "w") as f:
        json.dump(documents, f)

    print(f"Saved {len(documents)} documents to {file_path}")


class Command(BaseCommand):
    help = "Feed Terrarium sources to Vespa."
    if not os.path.exists(file_path):
        process_geojson_to_file(geojson_url, file_path)

    result = feed_file_to_vespa(file_path)
    if result["success"]:
        print(f"Success: {result['output']}")
    else:
        raise CommandError(f"Failed: {result['output']}")
