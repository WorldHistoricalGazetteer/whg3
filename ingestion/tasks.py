# ingestion/ingest.py
import requests
import gzip
import ijson
import logging

from celery import shared_task

from .transformers import NPRTransformer  # Use NPRTransformer for data transformation

logger = logging.getLogger(__name__)


def get_dataset_config(dataset_name):
    from .models import DatasetConfig
    try:
        return DatasetConfig.objects.get(dataset_name=dataset_name)
    except DatasetConfig.DoesNotExist:
        raise ValueError(f"Dataset config for '{dataset_name}' not found")


@shared_task
def ingest_gzipped_data_from_url(dataset_name, limit=None):
    from ingestion.models import NPR, Toponym, Attestation
    config = get_dataset_config(dataset_name)

    if not config:
        logger.error(f"Configuration for dataset '{dataset_name}' not found.")
        return
    logger.info(f"Starting ingestion for dataset: {dataset_name}")
    logger.info(f"Configuration: {config}")

    # Delete existing NPRs and their Attestations for the given dataset
    Attestation.objects.filter(npr__source=config).delete()
    NPR.objects.filter(source=config).delete()
    logger.info(f"Deleted previous NPRs and their Attestations for dataset: {dataset_name}")

    url = config.url
    item_path = config.item_path

    try:
        with requests.get(url, stream=True) as response:
            logger.info(f"Fetching data from {url}")
            response.raise_for_status()  # Check for request errors
            # Decompress the gzip content
            with gzip.GzipFile(fileobj=response.raw, mode='rb') as f:
                logger.info(f"Decompressing data from {url}")
                graph_items = ijson.items(f, item_path)

                count = 0  # Counter for limiting the number of items
                for item in graph_items:
                    if limit is not None and count >= limit:
                        break  # Stop processing if the limit is reached
                    try:
                        # Transform the item using the corresponding transformer
                        # logger.info(f"Transforming item: {item}")
                        transformed_item, alternate_names = NPRTransformer.transformers[dataset_name](item)
                        logger.info(f"Transformed item: {transformed_item}")
                        logger.info(f"Alternate names: {alternate_names}")

                        # Save the transformed item to the database
                        npr_instance = NPR.create_npr(
                            source=config,
                            **transformed_item
                        )

                        if npr_instance:
                            logger.info(f"Successfully ingested item: {npr_instance}")

                            # Save the alternate toponyms
                            for name_data in alternate_names:
                                # Extract toponym details
                                toponym_text = name_data.pop('toponym')
                                language = name_data.pop('language', 'und')  # Default to 'und' (undefined) if missing
                                is_romanised = name_data.pop('is_romanised', False)

                                # Get or create the Toponym instance
                                toponym_instance = Toponym.create_toponym(
                                    toponym=toponym_text,
                                    language=language,
                                    is_romanised=is_romanised
                                )

                                # Create the attestation linking the NPR and the toponym
                                Attestation.create_attestation(
                                    npr=npr_instance,
                                    toponym=toponym_instance,
                                    start=name_data.get('start'),
                                    end=name_data.get('end')
                                )

                            logger.info(f"Successfully added toponyms for item: {npr_instance}")

                    except Exception as e:
                        logger.error(f"Error processing item: {e}")

                    count += 1

    except Exception as e:
        logger.error(f"Failed to fetch data from {url}: {e}")
    logger.info(f"Finished ingestion for dataset: {dataset_name}")
