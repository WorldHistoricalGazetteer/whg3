#!/usr/bin/env python3
"""
update_from_gazetteers.py

Management command to extend SpatialEntity with geospatial data from GitHub gazetteers.

- Downloads gazetteer files from periodo-places GitHub repository
- Tracks GitHub commit hashes to avoid reprocessing unchanged files
- Processes GeoJSON features and matches them to existing SpatialEntity records by URI
- Stores PostGIS geometry and bounding box polygon for efficient spatial queries
- Optimized version without tqdm but with progress reporting and batching
"""

import json
import requests
from typing import Dict, List, Optional

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.db import transaction

from periods.models import SpatialEntity, GazetteerTracker, Period


class Command(BaseCommand):
    help = "Update SpatialEntity with geospatial data from periodo-places gazetteers."

    GITHUB_API_BASE = "https://api.github.com/repos/periodo/periodo-places"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/periodo/periodo-places/master/gazetteers"
    BATCH_SIZE = 500  # Process features in batches

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reprocessing of all files regardless of commit hash',
        )
        parser.add_argument(
            '--files',
            nargs='+',
            help='Process only specific files (e.g., --files geonames.json pleiades.json)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of features to process per batch (default: 500)',
        )

    def handle(self, *args, **options):
        self.BATCH_SIZE = options['batch_size']
        self.stdout.write("Starting spatial entities update...")

        # Get list of gazetteer files
        gazetteer_files = self.get_gazetteer_files()
        if not gazetteer_files:
            self.stderr.write("No gazetteer files found.")
            return

        # Filter files if specific ones requested
        if options['files']:
            gazetteer_files = [f for f in gazetteer_files if f['name'] in options['files']]

        self.stdout.write(f"Found {len(gazetteer_files)} gazetteer files.")

        # Process each gazetteer file
        total_updated = 0
        for i, file_info in enumerate(gazetteer_files, 1):
            self.stdout.write(f"Processing file {i}/{len(gazetteer_files)}: {file_info['name']}")
            updated = self.process_gazetteer_file(file_info, options['force'])
            total_updated += updated

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {total_updated} spatial entities.")
        )

        # Now compute bounding boxes for periods
        self.compute_period_bboxes()

    def get_gazetteer_files(self) -> List[Dict]:
        """Get list of JSON files in the gazetteers directory"""
        try:
            url = f"{self.GITHUB_API_BASE}/contents/gazetteers"
            response = requests.get(url)
            response.raise_for_status()

            files = []
            for item in response.json():
                if item['type'] == 'file' and item['name'].endswith('.json'):
                    files.append({
                        'name': item['name'],
                        'sha': item['sha'],
                        'download_url': item['download_url']
                    })
            return files

        except requests.RequestException as e:
            self.stderr.write(f"Error fetching file list: {e}")
            return []

    def process_gazetteer_file(self, file_info: Dict, force: bool = False) -> int:
        """Process a single gazetteer file"""
        filename = file_info['name']
        current_sha = file_info['sha']

        # Check if we need to process this file
        try:
            tracker = GazetteerTracker.objects.get(filename=filename)
            if not force and tracker.commit_hash == current_sha:
                self.stdout.write(f"Skipping {filename} (no changes)")
                return 0
        except GazetteerTracker.DoesNotExist:
            tracker = GazetteerTracker(filename=filename)

        self.stdout.write(f"Downloading {filename}...")

        # Download and parse the gazetteer
        try:
            response = requests.get(file_info['download_url'])
            response.raise_for_status()
            gazetteer_data = response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            self.stderr.write(f"Error downloading {filename}: {e}")
            return 0

        # Get features and process in batches
        features = gazetteer_data.get('features', [])
        total_features = len(features)

        if total_features == 0:
            self.stdout.write(f"No features found in {filename}")
            return 0

        self.stdout.write(f"Processing {total_features} features from {filename} in batches of {self.BATCH_SIZE}...")

        total_updated = 0

        # Pre-load existing SpatialEntities for efficiency
        feature_ids = [f.get('id') for f in features if f.get('id')]
        existing_entities = {se.uri: se for se in SpatialEntity.objects.filter(uri__in=feature_ids)}
        self.stdout.write(f"Found {len(existing_entities)} matching spatial entities")

        # Process in batches
        for batch_start in range(0, total_features, self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE, total_features)
            batch = features[batch_start:batch_end]
            batch_num = (batch_start // self.BATCH_SIZE) + 1
            total_batches = (total_features + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            self.stdout.write(f"Processing batch {batch_num}/{total_batches} ({len(batch)} features)...")

            batch_updated = 0
            batch_skipped = 0
            batch_errors = 0

            with transaction.atomic():
                for feature in batch:
                    result = self.process_feature(feature, filename, existing_entities)
                    if result == 'updated':
                        batch_updated += 1
                    elif result == 'skipped':
                        batch_skipped += 1
                    else:
                        batch_errors += 1

                # Update tracker after successful batch
                tracker.commit_hash = current_sha
                tracker.save()

            total_updated += batch_updated

            self.stdout.write(
                f"Batch {batch_num} complete: {batch_updated} updated, "
                f"{batch_skipped} skipped, {batch_errors} errors"
            )

        self.stdout.write(f"Finished {filename}: {total_updated} entities updated")
        return total_updated

    def process_feature(self, feature: Dict, source_filename: str, existing_entities: Dict) -> str:
        """
        Process a single GeoJSON feature
        Returns: 'updated', 'skipped', or 'error'
        """
        try:
            # Extract feature ID - this should match SpatialEntity.uri
            feature_id = feature.get('id')
            if not feature_id:
                return 'skipped'

            # Check if we have a matching SpatialEntity
            spatial_entity = existing_entities.get(feature_id)
            if not spatial_entity:
                return 'skipped'

            # Skip if already processed from this source (unless forcing)
            if spatial_entity.gazetteer_source == source_filename and spatial_entity.geometry:
                return 'skipped'

            # Extract geometry
            geometry_data = feature.get('geometry')
            if not geometry_data:
                return 'skipped'

            # Convert to Django GEOSGeometry
            try:
                geometry = GEOSGeometry(json.dumps(geometry_data))
                spatial_entity.geometry = geometry
                spatial_entity.gazetteer_source = source_filename
            except Exception as e:
                self.stderr.write(f"Error processing geometry for {feature_id}: {e}")
                return 'error'

            # Calculate and store bounding box as polygon
            bbox_polygon = self.create_bbox_polygon(geometry)
            if bbox_polygon:
                spatial_entity.bbox = bbox_polygon

            # Update label if available and not already set
            properties = feature.get('properties', {})
            if properties.get('name') and not spatial_entity.label:
                spatial_entity.label = properties['name']

            spatial_entity.save()
            return 'updated'

        except Exception as e:
            self.stderr.write(f"Error processing feature {feature.get('id', 'unknown')}: {e}")
            return 'error'

    def create_bbox_polygon(self, geometry: GEOSGeometry) -> Optional[Polygon]:
        """Create a bounding box polygon from geometry extent"""
        try:
            extent = geometry.extent  # Returns (xmin, ymin, xmax, ymax)

            # Create a polygon from the bounding box coordinates
            bbox_coords = [
                (extent[0], extent[1]),  # southwest
                (extent[0], extent[3]),  # northwest
                (extent[2], extent[3]),  # northeast
                (extent[2], extent[1]),  # southeast
                (extent[0], extent[1])  # close the ring
            ]

            return Polygon(bbox_coords)

        except Exception as e:
            self.stderr.write(f"Error creating bbox polygon: {e}")
            return None

    def compute_period_bboxes(self):
        """Compute bounding boxes for periods based on their spatial entities"""
        self.stdout.write("Computing bounding boxes for periods...")

        # Get all periods that have spatial coverage with geometries
        periods_with_spatial = Period.objects.filter(
            spatialCoverage__geometry__isnull=False
        ).distinct()

        total_periods = periods_with_spatial.count()
        if total_periods == 0:
            self.stdout.write("No periods with spatial geometries found.")
            return

        self.stdout.write(f"Processing {total_periods} periods with spatial coverage...")

        updated_periods = 0
        batch_size = 100

        for batch_start in range(0, total_periods, batch_size):
            batch_end = min(batch_start + batch_size, total_periods)
            batch_periods = periods_with_spatial[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (total_periods + batch_size - 1) // batch_size

            self.stdout.write(f"Processing period batch {batch_num}/{total_batches}...")

            batch_updated = 0

            with transaction.atomic():
                for period in batch_periods:
                    # Get all geometries for this period's spatial entities
                    spatial_entities = period.spatialCoverage.filter(geometry__isnull=False)

                    if not spatial_entities.exists():
                        continue

                    try:
                        # Collect all geometries
                        geometries = []
                        for entity in spatial_entities:
                            if entity.geometry:
                                geometries.append(entity.geometry)

                        if not geometries:
                            continue

                        # Create union of all geometries to get combined extent
                        if len(geometries) == 1:
                            combined_geom = geometries[0]
                        else:
                            # Union all geometries
                            combined_geom = geometries[0]
                            for geom in geometries[1:]:
                                try:
                                    combined_geom = combined_geom.union(geom)
                                except Exception as e:
                                    # If union fails, skip this geometry
                                    self.stderr.write(f"Warning: Could not union geometry for period {period.id}: {e}")
                                    continue

                        # Create bounding box polygon from combined extent
                        bbox_polygon = self.create_bbox_polygon(combined_geom)

                        if bbox_polygon:
                            # Check if Period model has bbox field
                            if hasattr(period, 'bbox'):
                                period.bbox = bbox_polygon
                                period.save()
                                batch_updated += 1
                            else:
                                self.stderr.write("Period model does not have bbox field. Add it to the model first.")
                                return

                    except Exception as e:
                        self.stderr.write(f"Error computing bbox for period {period.id}: {e}")
                        continue

            updated_periods += batch_updated
            self.stdout.write(f"Period batch {batch_num} complete: {batch_updated} periods updated")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully computed bounding boxes for {updated_periods} periods.")
        )