# validation/views.py
import os
import pandas as pd
import json
import codecs
import logging
import subprocess
import uuid
import ijson
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from pyld import jsonld
from .tasks import validate_feature_batch, cleanup
import redis
import sys
from .tLPF_mappings import tLPF_mappings
from shapely import wkt
from shapely.geometry import mapping
import geojson

logger = logging.getLogger('validation')

def get_redis_client():
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

def get_memory_size(obj):
    """Estimate the memory size of an object."""
    return sys.getsizeof(obj) + sum(sys.getsizeof(v) for v in obj.values() if isinstance(obj, dict))

def json_feature_count(file_path):
    """ Count the number of features in a JSON FeatureCollection file."""
    try:
        with open(file_path, 'r') as file:
            feature_count = sum(1 for _ in ijson.items(file, 'features.item'))
            return feature_count
    except (IOError, ValueError) as e:
        logger.error(f"Error counting features in JSON file: {e}")
        raise

def get_file_info(file_path):
    info = {}
    
    try:
        # Get MIME type
        mime_type_result = subprocess.run(
            ['file', '--mime-type', '-b', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        info['mime_type'] = mime_type_result.stdout.strip()

        # Get MIME encoding
        mime_encoding_result = subprocess.run(
            ['file', '--mime-encoding', '-b', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        info['mime_encoding'] = mime_encoding_result.stdout.strip()

        logger.debug(f"File info: {info}")
        return info
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running file command: {e}")
        return {'mime_type': None, 'mime_encoding': None}
    except Exception as e:
        logger.error(f"Unexpected error while getting file information: {e}")
        return {'mime_type': None, 'mime_encoding': None}
    return LPF_file_path
    
def parse_to_LPF(delimited_file_path, ext):
    try:
        _, ext = os.path.splitext(delimited_file_path)
        ext = ext.lower()
        separator = ',' if ext == '.csv' else '\t' if ext == '.tsv' else None

        lpf_file_path = delimited_file_path.replace(ext, '.jsonld')
        logger.debug(f"Processing [separator: {separator}] file '{delimited_file_path}'.")

        converters = {key: mapping['converter'] for key, mapping in tLPF_mappings.items()}

        def get_df_reader():
            configuration = {
                'nrows': settings.VALIDATION_CHUNK_ROWS,
                'header': 0,
                'true_values': ['true', 'True'],
                'false_values': ['false', 'False'],
                'na_values': ['NA', 'NaN'],
                'na_filter': False
            }
            try: # read_excel does not support chunk-size, so implementation requires line-reading
                skiprows = 0
                while True:
                    if separator:
                        logger.debug(f"Reading from CSV.")
                        df_chunk = pd.read_csv(delimited_file_path, skiprows=skiprows, **configuration, sep=separator, encoding='utf-8', skipinitialspace=True)
                    else:
                        logger.debug(f"Reading from Excel.")
                        df_chunk = pd.read_excel(delimited_file_path, skiprows=skiprows, **configuration, sheet_name=0)
                    skiprows += settings.VALIDATION_CHUNK_ROWS
                    if df_chunk.empty:
                        break
                    yield df_chunk

            except pd.errors.EmptyDataError:
                logger.warning("Empty chunk encountered; stopping.")
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error detected: {e}")
                raise
            except pd.errors.ParserError as e:
                logger.error(f"Parsing error detected: {e}")
                raise 
            except Exception as e:
                logger.error(f"Error reading file {delimited_file_path}: {e}")
                raise
            
        def assign_nested_value(d, keys, value):
            """
            Assigns a value to a nested dictionary, creating any intermediate keys as necessary.
            Initializes the nested structure based on the type of the final value.
            """    

            for i, key in enumerate(keys[:-1]):
                next_key = keys[i + 1]
                
                if isinstance(d, dict) and key not in d:
                    if isinstance(next_key, int):
                        d[key] = [{}] * (next_key + 1)
                    else:
                        d[key] = {}
                    
                d = d[key]
                
            final_key = keys[-1]
            if isinstance(d, list) and final_key >= len(d):
                d.extend([{}])
            d[final_key] = value

        with open(lpf_file_path, 'w') as lpf_file:
            first_line = True  # To handle commas between records in feature array
            feature_count = 0

            # Write the opening of the JSON FeatureCollection
            lpf_file.write('{\n"type": "FeatureCollection",\n"features": [\n')
            logger.debug(f"Started writing output to '{lpf_file_path}'.")
        
            for chunk in get_df_reader():
        
                for _, record in chunk.iterrows():
                    record = record.to_dict()  # Convert row to a dictionary
                    # logger.debug(f"Processing record #{feature_count}: '{record}'.")
                    
                    # Apply converters: NB these cannot be applied during pd.read_excel due to the unhashable lists they produce
                    for key, converter in converters.items():
                        if key in record:
                            record[key] = converter(record[key])
        
                    # Create the nested JSON structure
                    lpf_feature = {}
                    for key, mapping in tLPF_mappings.items():
                        if key in record:
                            value = record[key]
                            if isinstance(value, list) or pd.notna(value):
                                nested_keys = [int(key) if key.isdigit() else key for key in mapping['lpf'].split('.')]
                                assign_nested_value(lpf_feature, nested_keys, value)                             
        
                    # Append additional names or types to the main record if needed
                    if 'names' in lpf_feature and isinstance(lpf_feature['names'], list) and 'additional_names' in lpf_feature:
                        lpf_feature['names'].extend(lpf_feature.pop('additional_names'))
                    if 'types' in lpf_feature and isinstance(lpf_feature['types'], list) and 'additional_types' in lpf_feature:
                        lpf_feature['types'].extend(lpf_feature.pop('additional_types'))
                    
                    if 'geometry' in lpf_feature:
                        lpf_feature['geometry']['type'] = 'Point'
                    else:
                        lpf_feature['geometry'] = None
                    
                    # Replace any existing geometry with geometry contained in any `geowkt`
                    if 'geowkt' in lpf_feature:
                        geometry = wkt.loads(lpf_feature['geowkt'])
                        geojson_geometry = mapping(geometry)
                        lpf_feature['geometry'] = geojson.dumps(geojson_geometry)
                        lpf_feature.pop('geowkt')
                        
                    # logger.debug(f"Processed record #{feature_count}: '{lpf_feature}'.")
        
                    # Write the JSON object to the file
                    if not first_line:
                        lpf_file.write(',\n')
                    else:
                        first_line = False
        
                    json.dump(lpf_feature, lpf_file, ensure_ascii=False)
                    feature_count += 1
        
            # Write the closing of the JSON FeatureCollection
            lpf_file.write('\n]}\n')

        logger.debug(f"fLPF file '{delimited_file_path}' converted to LPF and written to '{lpf_file_path}'.")
        return lpf_file_path, feature_count

    except Exception as e:
        logger.error(f"Error processing file {delimited_file_path}: {e}")
        raise

def validate_file(request, file_path, original_file_name):
    
    try:
        with codecs.open(settings.LPF_SCHEMA_PATH, 'r', 'utf8') as schema_file:
            schema = json.load(schema_file)
        with codecs.open(settings.LPF_CONTEXT_PATH, 'r', 'utf8') as context_file:
            context = json.load(context_file)
    except (IOError, json.JSONDecodeError) as e:
        message = f"Error reading schema or context file: {e}"
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
    
    file_info = get_file_info(file_path)
    
    if file_info['mime_type'] is None:
        message = "Unable to determine the content type of the file."
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
    elif file_info['mime_type'] not in settings.VALIDATION_SUPPORTED_TYPES:
        message = f"The detected content type (<b>{file_info['mime_type']}</b>) is not supported."
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500) 
    
    # Preliminary utf-8 encoding test: further validation is performed when reading non-JSON files
    allowed_encodings = settings.VALIDATION_ALLOWED_ENCODINGS + ['binary'] # 'binary' required for spreadsheets when using Unix file command
    if file_info['mime_encoding'] is None:
        message = "Unable to determine the encoding type of the file."
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
    elif file_info['mime_encoding'] not in allowed_encodings:
        message = f"The detected encoding type (<b>{file_info['mime_encoding']}</b>) is not supported. Please ensure that the file is encoded as UTF or ASCII."
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
    
    # Convert delimited files to LPF JSON
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    try:
        if 'json' in ext: # mime type is not a reliable determinant of JSON
            delimited_file_path = ''
            feature_count = json_feature_count(file_path)
            logger.debug(f'JSON contains {feature_count} features.')
        else:
            delimited_file_path = file_path
            file_path, feature_count = parse_to_LPF(file_path, ext)
    except Exception as e:
        message = f"Error converting delimited text to LPF: {e}"
        logger.error(message)
        return JsonResponse({"status": "failed", "message": message}, status=500)
        
    # Initialise Redis client
    redis_client = get_redis_client()
    task_id = f"validation_task_{uuid.uuid4()}"
    
    # Schedule the cleanup task
    cleanup_task_result = cleanup.apply_async((task_id,), countdown=settings.VALIDATION_TIMEOUT)
    cleanup_task_id = cleanup_task_result.id
    
    # TODO: Read any CSL citation and store as JSON in redis_client ?
    
    # Store task details in Redis
    redis_client.hset(task_id, mapping={
        'status': 'in_progress',
        'start_time': timezone.now().isoformat(),
        'all_queued': 'false',
        'total_features': feature_count,
        'delimited_file_path': delimited_file_path,
        'file_path': file_path,
        'original_file_name': original_file_name,
        'cleanup_task_id': cleanup_task_id,
    })
    logger.debug('Redis client initialised.')

    try:
        # Process each batch of features as a separate Celery task
        for feature_batch in read_json_features_in_batches(file_path, task_id):
            # The following line could be implemented if the LP Ontology were correct
            #feature_batch = [jsonld.compact(feature, context) for feature in feature_batch]
            validate_feature_batch.delay(feature_batch, schema, task_id)
            feature_tally = len(feature_batch)
            redis_client.hincrby(task_id, 'queued_features', feature_tally)
            redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
            
        redis_client.hset(task_id, 'all_queued', 'true')
        redis_client.hset(task_id, 'last_update', timezone.now().isoformat())
            
    except Exception as e:
        full_error = f"Batch processing error: {str(e)}"
        logger.error(full_error)
        redis_client.rpush(f"{task_id}_errors", full_error)
            
        redis_client.hset(task_id, mapping={
            'status': 'failed',
            'end_time': timezone.now().isoformat()
        })

        return JsonResponse({"status": "failed", "message": str(e)}, status=500)

    return JsonResponse({"status": "in_progress", "task_id": task_id})

def read_json_features_in_batches(file_path, task_id):
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
