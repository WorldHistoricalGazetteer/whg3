# ingestion/ingest.py
import csv
import io
import os
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

import requests
import gzip
import ijson
import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import caches

from .transformers import NPRTransformer  # Use NPRTransformer for data transformation

logger = logging.getLogger(__name__)


class StreamFetcher:
    def __init__(self, file, cache_key):
        self.file_url = file['url']  # URL of the file to fetch
        self.file_type = file['file_type']  # Type of the file (json, csv, xml)
        self.file_name = file.get('file_name', None)  # Name of required file inside a ZIP archive
        self.item_path = file.get('item_path', None)  # Path to the items in a JSON file
        self.fieldnames = file.get('fieldnames', None)  # Fieldnames for CSV files
        self.delimiter = file.get('delimiter', '\t')  # Delimiter for CSV files
        self.cache_key = cache_key  # Unique cache key for this dataset
        self.cache = caches['remote_datasets']
        self.local_cache = None

    def get_stream(self):
        if self.file_url.endswith('.gz'):
            return self._get_gzip_stream()
        elif self.file_url.endswith('.zip'):
            return self._get_zip_stream()
        else:
            raise ValueError("Unsupported file format")

    def _get_gzip_stream(self):
        # Directly stream gzip file from URL
        response = requests.get(self.file_url, stream=True)
        response.raise_for_status()
        return gzip.GzipFile(fileobj=response.raw)

    def _get_zip_stream(self):
        # Check if the file is cached
        cache_file_path = self.cache.get(self.cache_key)

        if not cache_file_path:
            try:
                # Create a temporary file in the cache directory
                cache_dir = settings.CACHES['remote_datasets']['LOCATION']
                cache_file_path = os.path.join(cache_dir, f"{self.cache_key}.zip")

                with requests.get(self.file_url, stream=True) as response:
                    response.raise_for_status()
                    with open(cache_file_path, 'wb') as cache_file:
                        for chunk in response.iter_content(chunk_size=8192):
                            cache_file.write(chunk)

                # Cache the file path in Django cache
                self.cache.set(self.cache_key, cache_file_path)

            except Exception as e:
                # Clean up if something goes wrong
                if os.path.exists(cache_file_path):
                    os.remove(cache_file_path)
                raise e

        # Open the zip file and return the stream of the specified file inside
        with zipfile.ZipFile(cache_file_path, 'r') as zip_file:
            if self.file_name not in zip_file.namelist():
                raise ValueError(f"{self.file_name} not found in the ZIP archive")
            return zip_file.open(self.file_name)

    def get_items(self):
        """
        Parse the stream and yield items based on format (json, csv, or xml).
        """
        stream = self.get_stream()
        format_type = self.file_type

        if format_type == 'json':
            return self._parse_json_stream(stream)
        elif format_type == 'csv':
            return self._parse_csv_stream(stream)
        elif format_type == 'xml':
            return self._parse_xml_stream(stream)
        else:
            raise ValueError("Unsupported format type")

    def _parse_json_stream(self, stream):
        # Using ijson for efficient JSON parsing from stream
        parser = ijson.items(stream, self.item_path)
        for item in parser:
            yield item

    def _parse_csv_stream(self, stream):
        # Parse CSV from stream
        wrapper = io.TextIOWrapper(stream, encoding='utf-8', errors='replace')
        csv_reader = csv.DictReader(wrapper, delimiter=self.delimiter, fieldnames=self.fieldnames)
        for row in csv_reader:
            yield row

    def _parse_xml_stream(self, stream):
        # Parse XML incrementally from stream
        for event, elem in ET.iterparse(stream, events=('end',)):
            if elem.tag == 'item':  # Assuming the root element of interest is <item>
                yield elem
                elem.clear()  # Free memory


def get_dataset_config(dataset_name):
    for config in settings.REMOTE_DATASET_CONFIGS:
        if config['dataset_name'] == dataset_name:
            return config
    raise ValueError(f"Dataset config for '{dataset_name}' not found")


@shared_task
def process_dataset(dataset_name, limit=None):
    config = get_dataset_config(dataset_name)
    if not config:
        logger.error(f"Configuration for dataset '{dataset_name}' not found.")
        return
    logger.info(f"Configuration: {config}")
    logger.info(f"Starting ingestion for dataset: {dataset_name}")

    for index, file in enumerate(config['files']):
        try:

            # # Clear existing records for the dataset
            # Attestation.objects.filter(npr__source=dataset_name).delete()
            # NPR.objects.filter(source=config).delete()
            # logger.info(f"Deleted previous NPRs and their Attestations for dataset: {dataset_name}")

            fetcher = StreamFetcher(file, cache_key=f"{dataset_name}_{index}")
            logger.debug(f"Instantiated fetcher: {fetcher}")
            transform_and_ingest(fetcher.get_items(), limit, dataset_name, index)

        except Exception as e:
            logger.error(f"Failed to fetch data from {file['url']}: {e}")

    logger.info(f"Finished ingestion for dataset: {dataset_name}")


def transform_and_ingest(items, limit, dataset_name, index=0):
    from ingestion.models import NPR, Toponym, Attestation
    count = 0  # Counter for limiting the number of items
    for item in items:
        if limit is not None and count >= limit:
            break  # Stop processing if the limit is reached
        try:
            # Transform the item using the corresponding transformer
            logger.info(f"Transforming item: {item}")
            transformed_item, alternate_names = NPRTransformer.transformers[dataset_name][index](item)
            logger.info(f"Transformed item: {transformed_item}")
            logger.info(f"Alternate names: {alternate_names}")

            # Save the transformed NPR to the database (or get existing)
            npr_instance = NPR.create_npr(
                source=dataset_name,
                **transformed_item
            )

            if npr_instance:
                logger.info(f"Successfully ingested or fetched NPR: {npr_instance}")

                if alternate_names:
                    # Save the alternate toponyms
                    for name_data in alternate_names:
                        # Get or create the Toponym instance
                        toponym_instance = Toponym.create_toponym(
                            toponym=name_data.pop('toponym'),
                            language=name_data.pop('language', 'und'),  # Default to 'und' (undefined) if missing
                            is_romanised=name_data.pop('is_romanised', False)
                        )

                        # Create the attestation linking the NPR and the toponym
                        Attestation.create_attestation(
                            npr=npr_instance,
                            toponym=toponym_instance,
                            **name_data  # Pass the remaining data as keyword arguments
                        )

                    logger.info(f"Successfully added toponyms for item: {npr_instance}")
                else:
                    logger.info(f"No alternate names found for item: {npr_instance}")

        except Exception as e:
            logger.error(f"Error processing item: {e}")

        count += 1
