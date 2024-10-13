# ingestion/ingest.py
import csv
import io
import os
import traceback
import xml.etree.ElementTree as ET
import zipfile

import requests
import gzip
import ijson
import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import caches

from .models import ToponymLookup
from .transformers import NPRTransformer  # Use NPRTransformer for data transformation

logger = logging.getLogger(__name__)


class StreamFetcher:
    def __init__(self, file, cache_key):
        self.file_url = file['url']  # URL of the file to fetch
        self.file_type = file['file_type']  # Type of the file (json, csv, xml)
        self.filter = file.get('filter', None)  # Filter to apply to triples
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
        elif format_type == 'nt':
            return self._parse_nt_stream(stream)
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
            if elem.tag == 'place':  # Assuming the root element of interest is <item>
                yield elem
                elem.clear()  # Free memory

    def _split_triple(self, line):
        parts = line.rstrip(' .').split(' ', 2)

        if len(parts) != 3:
            raise ValueError("Triple must have exactly three components")

        subject, predicate, obj = parts
        return subject, predicate, obj

    def _parse_nt_stream(self, stream):
        wrapper = io.TextIOWrapper(stream, encoding='utf-8', errors='replace')

        for line in wrapper:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            try:
                # Split N-Triple line into three components (subject, predicate, object)
                subject, predicate, obj = self._split_triple(line)
                if self.filter and not predicate in self.filter:
                    continue
                yield {
                    'subject': subject.strip('<>'),
                    'predicate': predicate.strip('<>'),
                    'object': obj.strip('<>')
                }
            except ValueError as e:
                logger.error(f"Failed to parse N-Triple line: {line}. Error: {e}")
                continue


def get_dataset_config(dataset_name):
    for config in settings.REMOTE_DATASET_CONFIGS:
        if config['dataset_name'] == dataset_name:
            return config
    raise ValueError(f"Dataset config for '{dataset_name}' not found")


@shared_task
def process_dataset(dataset_name, limit=None):
    from ingestion.models import Attestation, NPR, Toponym
    config = get_dataset_config(dataset_name)
    if not config:
        logger.error(f"Configuration for dataset '{dataset_name}' not found.")
        return
    logger.info(f"Configuration: {config}")
    logger.info(f"Starting ingestion for dataset: {dataset_name}")

    # Clear existing records for the dataset
    Attestation.objects.filter(npr__source=dataset_name).delete()
    NPR.objects.filter(source=config).delete()
    logger.info(f"Deleted previous NPRs and their Attestations for dataset: {dataset_name}")

    for index, file in enumerate(config['files']):
        try:
            fetcher = StreamFetcher(file, cache_key=f"{dataset_name}_{index}")
            logger.debug(f"Instantiated fetcher: {fetcher}")
            transform_and_ingest(fetcher.get_items(), limit, dataset_name, index)

        except Exception as e:
            logger.error(f"Failed to fetch data from {file['url']}: {e}")

    logger.info(f"Finished ingestion for dataset: {dataset_name}")

    if dataset_name == 'TGN':
        NPR.compute_ccodes()

        # Update Attestation toponym_ids by fetching from Toponym using source_toponym_id
        for attestation in Attestation.objects.filter(npr__source=dataset_name):
            try:
                # Fetch and update the toponym based on the source_toponym_id
                attestation.toponym = ToponymLookup.objects.get(source_toponym_id=attestation.source_toponym_id).toponym
                attestation.save()
            except ToponymLookup.DoesNotExist:
                logger.error(f"Toponym with temp_id {attestation.source_toponym_id} not found")

        # After updating all the toponym_ids, update the primary names for all NPR instances
        NPR.update_primary_names()


def transform_and_ingest(items, limit, dataset_name, index=0):
    from ingestion.models import NPR, Toponym, Attestation, ToponymLookup
    count = 0  # Counter for limiting the number of items
    for item in items:
        if limit is not None and count >= limit:
            break  # Stop processing if the limit is reached
        try:
            # Transform the item using the corresponding transformer
            # logger.info(f"Transforming item: {item}")
            transformed_item, alternate_names = NPRTransformer.transformers[dataset_name][index](item)
            # logger.info(f"Transformed item: {transformed_item}")
            # logger.info(f"Alternate names: {alternate_names}")

            npr_instance = None
            if transformed_item:
                # Save the transformed NPR to the database (or get existing)
                npr_instance = NPR.create_or_update(
                    source=dataset_name,
                    **transformed_item
                )

                # if npr_instance:
                #     logger.info(f"Successfully ingested or fetched NPR: {npr_instance}")

            if alternate_names:
                # Save the alternate toponyms
                for name_data in alternate_names:
                    if 'toponym' in name_data:
                        # Get or create the Toponym instance
                        toponym_instance = Toponym.create_toponym(
                            toponym=name_data.pop('toponym'),
                            language=name_data.pop('language', None),  # Default to 'und' (undefined) if missing
                            is_romanised=name_data.pop('is_romanised', False),
                        )

                        ToponymLookup.objects.create(
                            toponym=toponym_instance,
                            source_toponym_id=name_data.get('source_toponym_id', None),
                        )
                    else:
                        toponym_instance = None

                    name_data = {**name_data, 'source': dataset_name, 'toponym': toponym_instance}
                    if npr_instance:
                        # Create the attestation linking the NPR and the toponym
                        Attestation.create_or_update_attestation(
                            npr=npr_instance,
                            **name_data  # Pass the remaining data as keyword arguments
                        )

            #     logger.info(f"Successfully added toponyms for item: {npr_instance}")
            # else:
            #     logger.info(f"No alternate names found for item: {npr_instance}")

        except Exception as e:
            error_message = (
                f"Error processing NPR instance:\n"
                f"Item: {item}\n"
                f"Exception: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            logger.error(error_message)

        count += 1
