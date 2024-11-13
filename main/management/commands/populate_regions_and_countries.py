import json
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import transaction
from pathlib import Path
from areas.models import Country, Area


class Command(BaseCommand):
    help = "Populate Region table from JSON, update Country table with Region IDs, and calculate bbox values."

    def handle(self, *args, **options):
        json_path = Path('media/data/regions_countries.json')

        with open(json_path) as f:
            self.data = json.load(f)  # Store data as an instance attribute

        self.update_areas()
        self.calculate_bboxes()

    def update_areas(self):
        self.stdout.write("Updating Areas (Regions) table from JSON data...")
        region_ids_from_json = {region_data["id"] for region_data in self.data[0]['children']}

        with transaction.atomic():
            for region_data in self.data[0]['children']:
                if region_data["id"] in region_ids_from_json:
                    try:
                        area = Area.objects.get(id=region_data["id"])
                        area.ccodes = region_data["ccodes"]  # Country codes associated with this region
                        area.save(update_fields=["ccodes"])
                        self.stdout.write(f"Updated Area (Region): {area.title}")
                    except Area.DoesNotExist:
                        self.stdout.write(f"Area (Region) with ID {region_data['id']} does not exist.")

    def calculate_bboxes(self):
        self.stdout.write("Calculating bbox values for Country and Area (Region) tables...")

        region_ids_from_json = {region_data["id"] for region_data in self.data[0]['children']}

        # Calculate bbox for each Country
        for country in Country.objects.all():
            if not country.bbox and country.mpoly:
                if isinstance(country.mpoly, (Polygon, MultiPolygon)):  # Ensure valid geometry
                    country.bbox = country.mpoly.envelope  # Store the envelope of mpoly as bbox
                    country.save(update_fields=["bbox"])
                    self.stdout.write(f"Calculated bbox for Country {country.gnlabel}")
                else:
                    self.stdout.write(f"Invalid geometry for Country {country.gnlabel}: {type(country.mpoly)}")

        # Calculate bbox and geojson for each Area (Region) in the JSON list
        for area in Area.objects.filter(id__in=region_ids_from_json):
            # Collect multipolygons of all countries in this area
            area_countries = Country.objects.filter(iso__in=area.ccodes)
            multipolygons = []

            for country in area_countries:
                if country.mpoly:
                    if isinstance(country.mpoly, MultiPolygon):
                        # If the geometry is a MultiPolygon, extract individual Polygons
                        multipolygons.extend(country.mpoly)  # This flattens the MultiPolygon into Polygons
                    elif isinstance(country.mpoly, Polygon):
                        multipolygons.append(country.mpoly)  # Directly add Polygon objects
                    else:
                        self.stdout.write(
                            f"Skipping invalid geometry for Country {country.gnlabel}: {type(country.mpoly)}")

            if multipolygons:
                try:
                    # Now combine all individual Polygons into a single MultiPolygon
                    combined_mpoly = MultiPolygon(*multipolygons)  # Combine all Polygons into a MultiPolygon

                    # Debug: Verify combined geometry
                    self.stdout.write(f"Combined MultiPolygon: {combined_mpoly}")

                    area.geojson = json.loads(combined_mpoly.geojson)  # Update area (region)'s geojson

                    # Set area bbox as the bounding box of the combined multipolygon
                    area.bbox = combined_mpoly.envelope
                    area.save(update_fields=["geojson", "bbox"])
                    self.stdout.write(f"Calculated bbox and updated geojson for Area (Region) {area.title}")
                except TypeError as e:
                    self.stdout.write(f"Error combining multipolygons for Area {area.title}: {str(e)}")
