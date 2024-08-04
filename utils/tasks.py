# utils/tasks.py
# Generic Celery tasks and helpers

from __future__ import absolute_import, unicode_literals
import csv
import simplejson as json
import os
import zipfile
from copy import deepcopy

import pandas as pd
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core import serializers
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from areas.models import Area
from collection.models import Collection, CollPlace
from datasets.models import Dataset
from datasets.utils import makeNow
from main.models import DownloadFile, Log
from places.models import Place
from utils.emailing import new_emailer

logger = get_task_logger(__name__)
User = get_user_model()

def downloader(request, *args, **kwargs):
    logger.debug(f'downloader() user: {request.user}, request.POST: {request.POST}')
    dsid = request.POST.get('dsid')
    collid = request.POST.get('collid')
    user = request.user

    if request.method == 'POST':
        if request.is_ajax():
            logger.debug('AJAX request detected')
            format = request.POST.get('format', 'json')
            userid = user.id if user.is_authenticated else 1
            try:
                download_task = make_download.delay(
                    userid=userid,
                    username=user.username,
                    dsid=dsid,
                    collid=collid,
                    format=format
                )
                logger.info(f'Task sent to Celery, task_id: {download_task.task_id}')
                return HttpResponse(json.dumps({'task_id': download_task.task_id}), content_type='application/json')
            except Exception as e:
                logger.error(f'Error sending task to Celery: {e}')
                return HttpResponse(status=500)
        else:
            logger.info(f'Non-AJAX POST request, data: {request.POST}')
    elif request.method == 'GET':
        logger.info(f'GET request, data: {request.GET}')

def generate_zip_filename(data_dump_filename):
    try:
        base_name, _ = os.path.splitext(data_dump_filename)
        zip_filename = f'{base_name}.zip'
        logger.debug(f'Generated zip filename: {zip_filename}')
        return zip_filename
    except Exception as e:
        logger.error(f'Error generating zip filename: {e}')
        raise

def create_downloadfile_record(user, ds, coll, zip_filename):
    try:
        logger.debug(f'Creating DownloadFile record for user: {user}, dataset: {ds}, collection: {coll}, zip_filename: {zip_filename}')
        title = coll.title if coll and not ds else ds.title if ds else None
        DownloadFile.objects.create(
            user=user,
            dataset=ds,
            collection=coll,
            title=title,
            filepath=f'/{zip_filename}',
        )
        logger.info('DownloadFile record created successfully')
    except Exception as e:
        logger.error(f'Error creating DownloadFile record: {e}')
        raise

def filter_and_order(metadata_json, desired_fields):
    try:
        filtered_metadata = {field: metadata_json['fields'].get(field) for field in desired_fields}
        logger.debug(f'Filtered metadata: {filtered_metadata}')
        return filtered_metadata
    except Exception as e:
        logger.error(f'Error filtering metadata: {e}')
        raise

def dataset_to_json(dsid):
    try:
        dataset = Dataset.objects.get(id=dsid)
        dataset_json = json.loads(serializers.serialize('json', [dataset]))[0]
        desired_fields = ['title', 'creator', 'create_date', 'description', 'numrows', 'source', 'webpage']
        filtered_dataset = filter_and_order(dataset_json, desired_fields)
        filtered_dataset.update({
            'model': dataset_json['model'],
            'pk': dataset_json['pk']
        })
        logger.info(f'Dataset JSON: {filtered_dataset}')
        return filtered_dataset
    except Dataset.DoesNotExist as e:
        logger.error(f'Dataset with ID {dsid} does not exist: {e}')
        raise
    except Exception as e:
        logger.error(f'Error converting dataset to JSON: {e}')
        raise

def collection_to_json(collid):
    try:
        coll = Collection.objects.get(id=collid)
        metadata_json = json.loads(serializers.serialize('json', [coll]))[0]
        collection_fields = ['title', 'creator', 'created', 'description', 'keywords', 'rel_keywords', 'numrows', 'webpage']
        dataset_fields = ['title', 'creator', 'create_date', 'description', 'numrows', 'source', 'webpage']
        filtered_collection = filter_and_order(metadata_json, collection_fields)
        
        if coll.collection_class == 'dataset':
            filtered_collection['datasets'] = []
            for ds in coll.datasets.all():
                dataset_json = json.loads(serializers.serialize('json', [ds]))[0]
                filtered_dataset = filter_and_order(dataset_json, dataset_fields)
                filtered_collection['datasets'].append(filtered_dataset)
        
        filtered_collection.update({
            'model': metadata_json['model'],
            'pk': metadata_json['pk']
        })
        logger.info(f'Collection JSON: {filtered_collection}')
        return filtered_collection
    except Collection.DoesNotExist as e:
        logger.error(f'Collection with ID {collid} does not exist: {e}')
        raise
    except Exception as e:
        logger.error(f'Error converting collection to JSON: {e}')
        raise

def create_zipfile(data_dump_filename, dsid=None, collid=None):
    try:
        today = makeNow()
        metadata = dataset_to_json(dsid) if dsid else collection_to_json(collid)
        pretty_metadata = json.dumps(metadata, indent=1, sort_keys=False)
        dl_class = "Dataset" if dsid else "Collection"
        readme_content = (f'World Historical Gazetteer (WHG)\n{dl_class} Download\n'
                          f'data: {os.path.basename(data_dump_filename)}\n'
                          '********************************\n'
                          'This dataset conforms to the CC-BY 4.0 NC license.\n\n'
                          "This license enables reusers to distribute, remix, adapt, and build upon the material "
                          "in any medium or format for noncommercial purposes only, and only so long as attribution "
                          "is given to the creator. CC BY-NC includes the following elements:\n"
                          "* Attribution — You must give appropriate credit, provide a link to the license, and indicate "
                          "if changes were made.\n"
                          "* NonCommercial — You may not use the material for commercial purposes.\n\n"
                          "***********************************\n"
                          "Metadata:\n" + pretty_metadata)
        
        with open('README.txt', 'w') as f:
            f.write(readme_content)

        zipname = generate_zip_filename(data_dump_filename)
        with zipfile.ZipFile(zipname, 'w') as zipf:
            zipf.write('README.txt', arcname='README.txt')
            zipf.write(data_dump_filename, arcname=os.path.basename(data_dump_filename))
        
        os.remove('README.txt')
        os.remove(data_dump_filename)
        logger.info(f'Created zip file: {zipname}')
    except Exception as e:
        logger.error(f'Error creating zip file: {e}')
        raise

@shared_task(name="make_download", bind=True)
def make_download(self, *args, **kwargs):
    logger.info(f'make_download() args: {args}, kwargs: {kwargs}')
    
    try:
        user = User.objects.get(pk=kwargs['userid'])
    except User.DoesNotExist as e:
        logger.error(f'User with ID {kwargs["userid"]} does not exist: {e}')
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'msg': 'User not found', 'error': str(e)}
    
    collid = kwargs.get('collid')
    dsid = kwargs.get('dsid')
    req_format = kwargs.get('format', 'json')
    date = makeNow()

    try:
        if collid and not dsid:
            try:
                coll = Collection.objects.get(id=collid)
                qs = coll.places_all.all()
                total_operations = qs.count()
                fn = f'media/downloads/{user.id}_{collid}_{date}.json'
                
                with open(fn, 'w', encoding='utf-8') as outfile:
                    features = []
                    for i, p in enumerate(qs):
                        try:
                            geoms = p.geoms.all()
                            geometry = geoms[0].jsonb if len(geoms) == 1 else {
                                "type": "GeometryCollection",
                                "geometries": [g.jsonb for g in geoms]
                            }
                            anno = p.traces.filter(collection_id=collid, archived=False).first()
                            coll_place = CollPlace.objects.filter(collection=collid, place=p).first()
                            annotation = {
                                "place_id": p.id,
                                "sequence": coll_place.sequence if coll_place else None,
                                "note": anno.note if anno else "",
                                "relation": anno.relation if anno else [],
                                "start": anno.start if anno else "",
                                "end": anno.end if anno else "",
                                "created": anno.created.strftime('%Y-%m-%d') if anno else ""
                            } if anno else {}
                            rec = {
                                "type": "Feature",
                                "properties": {
                                    "id": p.id,
                                    "src_id": p.src_id,
                                    "title": p.title,
                                    "ccodes": p.ccodes,
                                    "annotation": annotation
                                },
                                "geometry": geometry,
                                "names": [n.jsonb for n in p.names.all()],
                                "types": [t.jsonb for t in p.types.all()],
                                "links": [ln.jsonb for ln in p.links.all()]
                            }
                            features.append(rec)
                            if i % 1000 == 0:
                                logger.info(f'Processed {i} places')
                        except Exception as e:
                            logger.error(f'Error processing place {p.id}: {e}')
                    
                    json.dump({"type": "FeatureCollection", "features": features}, outfile, ensure_ascii=False, indent=4)
                    create_downloadfile_record(user, None, coll, fn)
                
                create_zipfile(fn, collid=collid)
                logger.info('Download created successfully')
                return {'msg': 'Download created successfully'}
            
            except Collection.DoesNotExist as e:
                logger.error(f'Collection with ID {collid} does not exist: {e}')
                self.update_state(state='FAILURE', meta={'error': str(e)})
                return {'msg': 'Collection not found', 'error': str(e)}
            
        elif dsid and not collid:
            try:
                dataset = Dataset.objects.get(id=dsid)
                qs = dataset.places.all()
                total_operations = qs.count()
                fn = f'media/downloads/{user.id}_{dsid}_{date}.json'
                
                with open(fn, 'w', encoding='utf-8') as outfile:
                    features = []
                    for i, p in enumerate(qs):
                        try:
                            geoms = p.geoms.all()
                            geometry = geoms[0].jsonb if len(geoms) == 1 else {
                                "type": "GeometryCollection",
                                "geometries": [g.jsonb for g in geoms]
                            }
                            anno = p.traces.filter(dataset_id=dsid, archived=False).first()
                            annotation = {
                                "place_id": p.id,
                                "note": anno.note if anno else "",
                                "relation": anno.relation if anno else [],
                                "start": anno.start if anno else "",
                                "end": anno.end if anno else "",
                                "created": anno.created.strftime('%Y-%m-%d') if anno else ""
                            } if anno else {}
                            rec = {
                                "type": "Feature",
                                "properties": {
                                    "id": p.id,
                                    "src_id": p.src_id,
                                    "title": p.title,
                                    "ccodes": p.ccodes,
                                    "annotation": annotation
                                },
                                "geometry": geometry,
                                "names": [n.jsonb for n in p.names.all()],
                                "types": [t.jsonb for t in p.types.all()],
                                "links": [ln.jsonb for ln in p.links.all()]
                            }
                            features.append(rec)
                            if i % 1000 == 0:
                                logger.info(f'Processed {i} places')
                        except Exception as e:
                            logger.error(f'Error processing place {p.id}: {e}')
                    
                    json.dump({"type": "FeatureCollection", "features": features}, outfile, ensure_ascii=False, indent=4)
                    create_downloadfile_record(user, dataset, None, fn)
                
                create_zipfile(fn, dsid=dsid)
                logger.info('Download created successfully')
                return {'msg': 'Download created successfully'}
            
            except Dataset.DoesNotExist as e:
                logger.error(f'Dataset with ID {dsid} does not exist: {e}')
                self.update_state(state='FAILURE', meta={'error': str(e)})
                return {'msg': 'Dataset not found', 'error': str(e)}
            
        else:
            msg = 'Invalid parameters. Provide either dsid or collid.'
            logger.error(msg)
            self.update_state(state='FAILURE', meta={'error': msg})
            return {'msg': msg}
    
    except Exception as e:
        logger.error(f'An error occurred during download: {e}')
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'msg': 'Error during download', 'error': str(e)}
