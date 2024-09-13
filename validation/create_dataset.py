import os
import json
import re
import sys
import shutil
from time import sleep

import ijson
import logging
from django.conf import settings

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.db import connection, transaction, IntegrityError, DataError
import redis

from datasets.models import Dataset, DatasetFile
from datasets.utils import aliasIt, ccodesFromGeom
from main.models import Log

from places.models import PlaceGeom, PlaceWhen, PlaceLink, PlaceRelated, PlaceDescription, PlaceDepiction, PlaceName, \
    PlaceType, Place, Type

logger = logging.getLogger('validation')


def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)


def save_dataset(task_id):
    redis_client = get_redis_client()

    cleanup_paths = []  # Keep track of paths to clean up in case of failure

    try:
        # Retrieve stored form data from Redis
        dataset_metadata = redis_client.hgetall(f"{task_id}_metadata")
        dataset_metadata = {k.decode('utf-8'): v.decode('utf-8') for k, v in dataset_metadata.items()}

        logger.debug(f"Retrieved dataset metadata: {dataset_metadata}")

        uploaded_filename = dataset_metadata.get('uploaded_filename')
        jsonld_filepath = dataset_metadata.get('jsonld_filepath')
        delimited_filepath = dataset_metadata.get('delimited_filepath')

        cleanup_paths.append(jsonld_filepath)
        cleanup_paths.append(delimited_filepath)

        # Start a transaction to ensure atomicity
        with transaction.atomic():

            # Create Dataset object
            dataset = Dataset.objects.create(
                title=dataset_metadata['title'] or f"-- placeholder ({dataset_metadata['label']}) --",
                label=dataset_metadata['label'],
                description=dataset_metadata['description'] or '-- placeholder --',
                numrows=dataset_metadata['feature_count'],
                creator=dataset_metadata['creator'],
                source=dataset_metadata['source'],
                contributors=dataset_metadata['contributors'],
                uri_base=dataset_metadata['uri_base'],
                webpage=dataset_metadata['webpage'],
                pdf=dataset_metadata['pdf'],
                owner_id=int(dataset_metadata['owner_id']),
                ds_status='uploaded'
            )

        try:
            ds_insert(jsonld_filepath, dataset, task_id)
        except Exception as e:
            dataset.delete()
            raise

        # Log the creation
        Log.objects.create(
            category='dataset',
            logtype='ds_create',
            subtype='place',
            dataset_id=dataset.id,
            user_id=int(dataset_metadata['owner_id'])
        )

        # Define paths and filenames
        username = dataset_metadata.get('username', 'unknown_user')
        user_folder = os.path.join(settings.MEDIA_ROOT, f"user_{username}")

        # Cache mapdata
        cache_file_path = os.path.join(settings.CACHES['default']['LOCATION'], f"dataset-{dataset.id}-standard.json")
        try:
            shutil.copy(jsonld_filepath, cache_file_path)
            logger.debug(f"Copied {jsonld_filepath} to mapdata cache.")
            cleanup_paths.append(cache_file_path)
        except (OSError, shutil.Error) as e:
            logger.error(f"Failed to copy file to cache: {e}")
            raise

        # Ensure that the user folder exists
        os.makedirs(user_folder, exist_ok=True)

        def get_unique_filename(filename, new_ext=None):
            base, ext = os.path.splitext(filename)
            ext = new_ext or ext
            counter = 1
            new_filename = f"{base}{ext}"
            while os.path.exists(os.path.join(user_folder, new_filename)):
                new_filename = f"{base}_{counter}{ext}"
                counter += 1
            return new_filename

        def create_DatasetFile(file, format=dataset_metadata['format'], delimiter=None, header=""):
            DatasetFile.objects.create(
                dataset_id=dataset,
                file=file,
                rev=1,
                format=format,
                delimiter=delimiter,
                header=header.split(';'),
                numrows=dataset_metadata['feature_count'],
                df_status='uploaded'
            )

        if not delimited_filepath:  # No LPF conversion was done, simply move the uploaded file
            if jsonld_filepath:
                new_filename = get_unique_filename(uploaded_filename)
                destination_path = os.path.join(user_folder, new_filename)
                shutil.move(jsonld_filepath, destination_path)
                cleanup_paths.append(destination_path)
                logger.debug(f"Moved uploaded file to {destination_path}")
                create_DatasetFile(destination_path)
            else:
                logger.warning("No file to move as both jsonld_filepath and delimited_filepath are missing.")
        else:  # Move both files
            if delimited_filepath:
                new_filename = get_unique_filename(uploaded_filename)
                destination_path = os.path.join(user_folder, new_filename)
                shutil.move(delimited_filepath, destination_path)
                cleanup_paths.append(destination_path)
                logger.debug(f"Moved delimited file to {destination_path}")
                create_DatasetFile(destination_path, delimiter=dataset_metadata['separator'],
                                   header=dataset_metadata['header'])
            if jsonld_filepath:
                new_filename_jsonld = get_unique_filename(uploaded_filename, '.jsonld')
                destination_path_jsonld = os.path.join(user_folder, new_filename_jsonld)
                shutil.move(jsonld_filepath, destination_path_jsonld)
                cleanup_paths.append(destination_path_jsonld)
                logger.debug(f"Moved uploaded file to {destination_path_jsonld}")
                create_DatasetFile(destination_path_jsonld, format='json')

        redis_client.delete(f"{task_id}_metadata")
        # Do not use cleanup task yet - user may still be polling `get_task_status` to fetch the following URL
        dataset_places_url = reverse('datasets:ds_places', kwargs={'id': dataset.id})
        redis_client.hset(task_id, 'dataset_places_url', dataset_places_url)
        logger.debug(f"DatasetPlacesView URL: {dataset_places_url}")
        return

    except ObjectDoesNotExist as e:
        message = f"Dataset or Log object does not exist: {e}"
    except KeyError as e:
        message = f"Missing expected key in dataset metadata: {e}"
    except (OSError, shutil.Error) as e:
        message = f"File operation error: {e}"
    except Exception as e:
        message = f"Unexpected error occurred: {e}"

    # Cleanup files after failure
    for path in cleanup_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up {path}")
            except Exception as cleanup_err:
                logger.error(f"Failed to clean up {path}: {cleanup_err}")

    logger.error(message)
    redis_client.hset(task_id, 'insertion_error', message)


def ds_insert(jsonld_filepath, ds, task_id):
    places_already_exist = Place.objects.filter(dataset=ds.label).exists()
    if places_already_exist:
        message = f"Database already contains places for dataset '{ds.label}'. Cannot add more."
        logger.error(message)
        raise Exception(message)

    redis_client = get_redis_client()
    redis_client.hset(task_id, 'insert_start_time', timezone.now().isoformat())
    redis_client.hset(task_id, 'queued_features', ds.numrows)

    data_mappings = {
        'PlaceGeoms': ('Geom', 'geometry', lambda feat: [
            PlaceGeom(place=newpl, src_id=newpl.src_id, jsonb=g, geom=GEOSGeometry(json.dumps(g)))
            for g in feat['geometry']['geometries']] if feat['geometry']['type'] == 'GeometryCollection' else
        [PlaceGeom(place=newpl, src_id=newpl.src_id, jsonb=feat['geometry'],
                   geom=GEOSGeometry(json.dumps(feat['geometry'])))]),
        'PlaceWhens': ('When', 'when', lambda feat: [
            PlaceWhen(place=newpl, src_id=newpl.src_id, jsonb=feat['when'], minmax=newpl.minmax)]),
        'PlaceLinks': ('Link', 'links', lambda feat: [
            PlaceLink(place=newpl, src_id=newpl.src_id,
                      jsonb={"type": l['type'], "identifier": aliasIt(l['identifier'].rstrip('/'))})
            for l in feat['links']]),
        'PlaceRelated': ('Related', 'relations', lambda feat: [
            PlaceRelated(place=newpl, src_id=newpl.src_id, jsonb=r)
            for r in feat['relations']]),
        'PlaceDescriptions': ('Description', 'descriptions', lambda feat: [
            PlaceDescription(place=newpl, src_id=newpl.src_id, jsonb=des)
            for des in feat['descriptions']]),
        'PlaceDepictions': ('Depiction', 'depictions', lambda feat: [
            PlaceDepiction(place=newpl, src_id=newpl.src_id, jsonb=dep)
            for dep in feat['depictions']]),
        'PlaceNames': ('Name', 'names', lambda feat: [
            PlaceName(place=newpl, src_id=newpl.src_id, toponym=n['toponym'].split(',')[0].strip(), jsonb=n)
            for n in feat.get('names', []) if 'toponym' in n]),
        'PlaceTypes': ('Type', 'types', lambda feat: [
            PlaceType(place=newpl, src_id=newpl.src_id, jsonb=t, fclass=fc)
            for t, fc in zip(feat.get('types', []), fclass_list)])
    }

    errors = []

    # Start a transaction to ensure atomicity
    with transaction.atomic():
        try:
            for feature_batch in read_json_features_in_batches(jsonld_filepath):
                for feat in feature_batch:
                    title = re.sub(r'\(.*?\)', '', feat.get('properties', {}).get('title', ''))
                    geojson = feat.get('geometry')
                    ccodes = feat.get('properties', {}).get('ccodes', [])
                    if ccodes is None and geojson:
                        ccodes = ccodesFromGeom(geojson)
                    # logger.debug('ccodes: {ccodes}')
                    intervals, minmax = parse_dates(feat)
                    # logger.debug(f"datesobj: {datesobj}")
                    fclass_list = get_fclass_list(feat)
                    # logger.debug(f"fclass_list: {fclass_list}")

                    logger.debug(f"New Place from feature: {feat}")

                    newpl = Place(
                        src_id=feat.get('@id') if ds.uri_base in ['', None] or not feat.get('@id').startswith(
                            ds.uri_base) else feat.get('@id')[len(ds.uri_base):],
                        dataset=ds,
                        title=title,
                        fclasses=fclass_list,
                        ccodes=ccodes,
                        minmax=minmax,
                        timespans=intervals,
                        create_date=timezone.now()
                    )
                    newpl.save()
                    logger.debug(f'New place: {newpl}')

                    objs = {key: list(filter(None, [item for sublist in map(create_func, [feat]) for item in sublist]))
                            for key, (_, feat_key, create_func) in data_mappings.items()
                            if feat.get(feat_key)}

                    for model, obj_list in [(model, objs[key]) for key, (model, _, _) in data_mappings.items() if
                                            objs.get(key)]:
                        try:
                            with connection.cursor() as cursor:  # required to mitigate race-condition integrity errors
                                cursor.execute(f'LOCK TABLE place_{model.lower()} IN ACCESS EXCLUSIVE MODE')
                                model_class = globals()[f'Place{model}']
                                model_class.objects.bulk_create(obj_list)
                        except IntegrityError as e:
                            errors.append({"field": model, "error": str(e)})
                            raise IntegrityError(f"IntegrityError in database insertion for {model}: {e}")
                        except ValidationError as e:
                            errors.append({"field": model, "error": str(e)})
                            raise ValidationError(f"ValidationError in database insertion for {model}: {e}")
                        except DataError as e:
                            errors.append({"field": model, "error": str(e)})
                            raise DataError(f"Database insertion load for {model} failed on {newpl}: {e}")
                        except Exception as e:
                            errors.append({"field": model, "error": str(e)})
                            raise Exception(f"Unexpected error in database insertion for {model}: {e}")

                    redis_client.hincrby(task_id, 'queued_features', -1)

        except Exception as e:
            logger.debug(f"Failed to insert data into dataset: {e}")
            raise Exception(f"Failed to insert data into dataset: {e}, Errors: {errors}")


def parse_dates(feature):
    paths = [  # valid `when` locations
        ['when'],
        ['geometry', 'when'],
        ['geometries', 'when'],
        ['names', 'when'],
        ['types', 'when'],
        ['relations', 'when'],
        ['relations', 'related', 'when']
    ]

    timespans = []

    def reduce_timespan_to_years(timespan):

        def extract_year(date_str):
            if not date_str:
                return None

            match = re.match(r'^-?\d{1,4}$|^-\d{5,}', date_str)
            return int(match.group(0)) if match else None

        def extract_from_dates(dates):
            return {extract_year(dates.get(key)) for key in ('in', 'earliest', 'latest') if dates.get(key)}

        years = set()
        if 'start' in timespan:
            years.update(extract_from_dates(timespan['start']))
        if 'end' in timespan:
            years.update(extract_from_dates(timespan['end']))

        sorted_years = sorted(year for year in years if year is not None)

        return [sorted_years[0], sorted_years[-1]] if sorted_years else None

    def when_timespans(when_obj):
        return when_obj.get('timespans', []) if when_obj else []

    for path in paths:
        obj = feature
        for key in path[:-1]:
            obj = obj.get(key, [])
            if isinstance(obj, list):
                for item in obj:
                    timespans.extend(when_timespans(item.get(path[-1])))
                break
        else:
            timespans.extend(when_timespans(obj.get(path[-1])))

    unique_intervals = sorted(
        set(
            tuple(result) for timespan in timespans if (result := reduce_timespan_to_years(timespan)) is not None
        ),
        key=lambda x: (x[0], -x[1])  # Sort by start ascending, then by end descending
    )

    # Merge overlapping and contained intervals
    merged_intervals = []
    for start, end in unique_intervals:
        if merged_intervals:
            last_start, last_end = merged_intervals[-1]
            if start <= last_end:  # Overlapping or contained
                merged_intervals[-1][1] = max(last_end, end)
            else:
                merged_intervals.append([start, end])
        else:
            merged_intervals.append([start, end])

    all_years = [year for interval in merged_intervals for year in interval]
    minmax = [min(all_years), max(all_years)] if all_years else None

    return merged_intervals, minmax


def get_fclass_list(feat):
    # Mappings between GeoNames and Wikidata types
    geo_wd_mapping = {
        'A': ['Q56061', 'Q192611', 'Q102496', 'Q10864048', 'Q1799794', 'Q1149654', 'Q82794', 'Q15642541', 'Q217151'],
        'P': ['Q515', 'Q15310171', 'Q18511725', 'Q98929991', 'Q7930989', 'Q486972', 'Q3957', 'Q532', 'Q178342',
              'Q22698', 'Q2983893', 'Q13221722'],
        'S': ['Q41176', 'Q189004', 'Q168719', 'Q3957', 'Q16917', 'Q515', 'Q811979', 'Q220933', 'Q55488', 'Q13221722',
              'Q47168', 'Q32815', 'Q57821', 'Q23442'],
        'R': ['Q34442', 'Q728937', 'Q55488', 'Q22649', 'Q11053', 'Q41176', 'Q1457376', 'Q1078747', 'Q4119149'],
        'L': ['Q82794', 'Q2542546', 'Q15642541', 'Q131681', 'Q35657', 'Q19836241', 'Q27096235'],
        'T': ['Q8502', 'Q207326', 'Q145694', 'Q650118', 'Q54050', 'Q16917', 'Q11444', 'Q8502', 'Q1170715', 'Q189604',
              'Q24415136', 'Q2329'],
        'H': ['Q8502', 'Q4022', 'Q23397', 'Q12284', 'Q9131', 'Q124482', 'Q13100073', 'Q1232506', 'Q166620', 'Q283',
              'Q26557']
    }

    types = feat.get('types', [])

    fclass_list = []
    for t in types:
        identifier = t.get('identifier')
        if identifier and identifier.startswith('aat:'):
            aat_id = int(identifier[4:])
            # Check if the aat_id exists in the database
            if Type.objects.filter(aat_id=aat_id).exists():
                try:
                    fclass = get_object_or_404(Type, aat_id=aat_id).fclass
                    fclass_list.append(fclass)
                except Exception as e:
                    logger.error(f"Error retrieving fclass for aat_id {aat_id}: {e}")
            else:
                logger.warning(f"aat_id {aat_id} not found in Type model.")
        elif identifier:
            # Mapping from geo_wd_mapping
            mapped_fclass = next((fclass for fclass, wd_types in geo_wd_mapping.items() if identifier[3:] in wd_types),
                                 None)
            if mapped_fclass:
                fclass_list.append(mapped_fclass)
            else:
                logger.warning(f"Identifier {identifier} not found in geo_wd_mapping.")
        else:
            logger.warning(f"Invalid identifier format: {identifier}")

    return fclass_list


def get_memory_size(obj):
    """Estimate the memory size of an object."""
    return sys.getsizeof(obj) + sum(sys.getsizeof(v) for v in obj.values() if isinstance(obj, dict))


def read_json_features_in_batches(file_path):
    """
    Streams JSON features from a file and yields batches of complete `Feature` objects
    without loading the entire file into memory.
    """
    try:
        with open(file_path, 'r') as file:
            logger.debug(f'Opened {file_path}...')
            parser = ijson.items(file, 'features.item', use_float=True)
            feature_batch = []
            current_memory_size = 0

            logger.debug(f'Parsing batch from {file_path} with parser: {type(parser)}')
            for feature in parser:
                current_memory_size += get_memory_size(feature)
                feature_batch.append(feature)

                if current_memory_size >= settings.VALIDATION_BATCH_MEMORY_LIMIT:
                    # logger.debug(f'Yielding batch ({current_memory_size} bytes): {feature_batch}')
                    yield feature_batch
                    feature_batch = []
                    current_memory_size = 0

            # Yield any remaining features in the last batch
            if feature_batch:
                # logger.debug(f'Yielding final batch ({current_memory_size} bytes): {feature_batch}')
                yield feature_batch

    except (IOError, ValueError) as e:
        logger.error(f"Error reading JSON features in batches: {e}")
        raise
