import requests
from django.conf import settings
import logging

from requests.auth import HTTPBasicAuth

# Set up logger
logger = logging.getLogger('django')  # Or another logger name from your configuration


def format_doi(type, id):
    return f"{settings.DOI_PREFIX}/whg-{type}-{id}"

def format_url(type, id):
    if type == 'dataset':
        return f"{settings.URL_FRONT}datasets/{id}/places"
    elif type == 'collection_dataset':
        return f"{settings.URL_FRONT}collections/{id}/browse_ds"
    elif type == 'collection_place':
        return f"{settings.URL_FRONT}collections/{id}/browse_pl"
    elif type == 'resource':
        return f"{settings.URL_FRONT}resources/{id}/detail"
    else:
        return None

def draft_doi(metadata):
    logger.info(f"Starting to draft DOI for {metadata['title']}")  # Log the beginning of the process

    # Set the headers for the API request
    headers = {
        'Content-Type': 'application/vnd.api+json',
        'authorization': f"Basic {settings.DOI_ENCODED_CREDENTIALS}"
    }

    logger.info(f"Headers: {headers}")

    # Define the DOI data with mandatory, recommended, and optional fields
    doi_data = {
        "data": {
            "type": "dois",
            "attributes": {
                "event": "draft",  # Set the event to "draft" to create a draft DOI (defaults to this value in any case if not set)

                # Mandatory fields
                "doi": format_doi(metadata['type'], metadata['id']),  # DOI to be created
                "url": format_url(metadata['type'], metadata['id']),  # URL of the resource
                "creators": [{"name": creator} for creator in metadata['creators']],
                "titles": [{"title": metadata['title']}],
                "publisher": metadata['publisher'],
                "publicationYear": metadata['publication_year'],
                "types": {"resourceTypeGeneral": metadata['resource_type_general']},

                # Recommended fields
                # "subjects": [{"subject": subject} for subject in metadata.get('subjects', [])],
                # "contributors": [{"name": contributor} for contributor in metadata.get('contributors', [])],
                # "dates": [{"date": metadata['publication_year'], "dateType": "Issued"}],  # Add more as needed
                # "relatedIdentifiers": [
                #     {
                #         "relatedIdentifier": identifier['id'],
                #         "relatedIdentifierType": identifier['type'],
                #         "relationType": identifier['relation']
                #     } for identifier in metadata.get('related_identifiers', [])
                # ],
                # "descriptions": [{"description": metadata['description'], "descriptionType": "Abstract"}],
                # "geoLocations": [
                #     {
                #         "geoLocationPlace": geo['place'],
                #         "geoLocationPoint": {
                #             "pointLatitude": geo['latitude'],
                #             "pointLongitude": geo['longitude']
                #         }
                #     } for geo in metadata.get('geo_locations', [])
                # ],

                # Optional fields
                # "language": metadata.get('language'),
                # "alternateIdentifiers": [
                #     {
                #         "alternateIdentifier": identifier['id'],
                #         "alternateIdentifierType": identifier['type']
                #     } for identifier in metadata.get('alternate_identifiers', [])
                # ],
                # "rightsList": [{"rights": metadata['rights']} for rights in metadata.get('rights_list', [])],
                # "sizes": metadata.get('sizes'),
                # "formats": metadata.get('formats'),
                # "version": metadata.get('version'),
                # "fundingReferences": [
                #     {
                #         "funderName": fund['name'],
                #         "funderIdentifier": fund.get('identifier'),
                #         "funderIdentifierType": fund.get('identifierType')
                #     } for fund in metadata.get('funding_references', [])
                # ],
                # "relatedItems": [
                #     {
                #         "relatedItemIdentifier": item['id'],
                #         "relatedItemIdentifierType": item['type'],
                #         "relationType": item['relation']
                #     } for item in metadata.get('related_items', [])
                # ],
            }
        }
    }

    # Clean out None values from optional fields
    def remove_none(d):
        """Recursively remove None values from dictionaries and lists."""
        if isinstance(d, list):
            return [remove_none(v) for v in d if v is not None]
        elif isinstance(d, dict):
            return {k: remove_none(v) for k, v in d.items() if v is not None}
        return d

    # Send the POST request to DataCite API with cleaned data
    cleaned_doi_data = remove_none(doi_data)
    logger.debug(f"Sending DOI creation request with data: {cleaned_doi_data}")  # Log the DOI data being sent
    response = requests.post(
        settings.DOI_API_URL,
        json=cleaned_doi_data,
        headers=headers,
    )

    # Check the response status
    if response.status_code == 201:
        logger.info(f"DOI created successfully: {response.json()['data']['id']}")  # Log success
        return response.json()  # DOI created successfully
    else:
        logger.error(f"Failed to create DOI: {response.json()}")  # Log error
        return response.json()  # Handle errors (like invalid metadata)


def update_doi_state(type, id, action="register"):
    doi = format_doi(type, id)
    logger.info(f"Updating DOI {doi} to {action} state")  # Log the update action

    headers = {
        'Content-Type': 'application/vnd.api+json',
        'authorization': f"Basic {settings.DOI_ENCODED_CREDENTIALS}"
    }

    update_data = {
        "data": {
            "type": "dois",
            "attributes": {
                "event": action  # Change state to "register" or "publish"
            }
        }
    }

    # Send a PATCH request to update the DOI's state
    logger.debug(f"Sending request to update DOI state with data: {update_data}")  # Log the request data
    response = requests.patch(
        f"{settings.DOI_API_URL}/{doi}",
        json=update_data,
        headers=headers,
    )

    if response.status_code == 200:
        logger.info(f"DOI state updated successfully to {action}")  # Log success
        return response.json()  # DOI updated successfully
    else:
        logger.error(f"Failed to update DOI state: {response.json()}")  # Log error
        return response.json()  # Handle errors (e.g., invalid state transition)


def get_doi_state(type, id):
    doi = format_doi(type, id)
    logger.info(f"Getting state of DOI {doi}...")  # Log the request
    # Set the headers for the API request
    headers = {
        'Content-Type': 'application/vnd.api+json',
        'authorization': f"Basic {settings.DOI_ENCODED_CREDENTIALS}"
    }

    # Send the GET request to DataCite API to retrieve DOI metadata

    response = requests.get(
        f"{settings.DOI_API_URL}/{doi}",
        headers=headers,
    )

    if response.status_code == 200:
        # Parse the JSON response and extract the state
        doi_metadata = response.json()
        state = doi_metadata['data']['attributes'].get('state', 'not_found')
        logger.info(f"DOI {doi} state: {state}")
        return state
    else:
        # Log the error or return the error message
        logger.error(f"Failed to retrieve DOI {doi} state: {response.json()}")
        return response.json()  # Handle errors if the DOI cannot be retrieved