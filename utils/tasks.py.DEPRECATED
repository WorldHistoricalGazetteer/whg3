# utils/tasks.py
# generic celery tasks and helpers

from __future__ import absolute_import, unicode_literals
from django.conf import settings
from django.core import serializers
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from celery import shared_task
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
import csv, os, zipfile
from copy import deepcopy
import pandas as pd
import simplejson as json

from areas.models import Area
from collection.models import Collection, CollPlace
from datasets.models import Dataset
from datasets.utils import makeNow
from main.models import DownloadFile, Log
from places.models import Place

import json
import csv
from copy import deepcopy
from celery import shared_task
from celery.result import AsyncResult
import pandas as pd
from django.conf import settings
from utils.emailing import new_emailer

logger = get_task_logger(__name__)
es = settings.ES_CONN
User = get_user_model()

"""
  initiate make_download for datasets and collections
  called from download modals, ds_metadata.html
"""
def downloader(request, *args, **kwargs):
  logger.debug('downloader() user, request.POST', request.user, request.POST)
  dsid = request.POST.get('dsid') or None
  collid = request.POST.get('collid') or None
  user = request.user
  # POST *should* be the only case...
  if request.method == 'POST' and request.accepts('XMLHttpRequest'):
    logger.debug('ajax == True')
    format=request.POST['format']

    userid = request.user.id if request.user.is_authenticated else 1
    download_task = make_download.delay(
      userid=user.id,
      username=user.username,
      dsid=dsid or None,
      collid=collid or None,
      format=format or None
    )

    logger.debug('task to Celery', download_task.task_id)
    # return task_id
    obj={'task_id': download_task.task_id}
    logger.debug('obj from downloader()', obj)

    return HttpResponse(json.dumps(obj), content_type='application/json')

  elif request.method == 'POST' and not request.is_ajax:
    logger.debug('request.POST (not ajax)', request.POST)


  elif request.method == 'GET':
    logger.debug('request.GET', request.GET)

# give file a .zip extension
def generate_zip_filename(data_dump_filename):
    base_name, _ = os.path.splitext(data_dump_filename)
    zipname = base_name + '.zip'
    return zipname

# create a DownloadFile record
def create_downloadfile_record(user, ds, coll, zip_filename):
  # Determine the title based on whether it's a Collection or Dataset
  logger.debug(f'@ create_downloadfile_record: user:{user}, ds: {ds}, coll: {coll}, zip_filename: {zip_filename}') # DEBUG
  if coll and not ds:
    title = coll.title
  elif ds:
    title = ds.title
  else:
    title = None  # or some default value

  # Create the DownloadFile instance
  DownloadFile.objects.create(
    user=user,
    dataset=ds or None,
    collection=coll or None,
    title=title,
    filepath='/' + zip_filename,
  )

# return ordered dict of metadata fields
def filter_and_order(metadata_json, desired_fields):
  # Directly using dict as Python 3.7+ maintains order
  filtered = {field: metadata_json['fields'][field] for field in desired_fields if field in metadata_json['fields']}
  return filtered

# generate metadata for a single dataset
def dataset_to_json(dsid):
  dataset = Dataset.objects.get(id=dsid)
  dataset_json = json.loads(serializers.serialize('json', [dataset]))[0]  # Deserialize to get the first item

  # Define the fields you want to keep
  desired_fields = ['title', 'creator', 'create_date', 'description', 'numrows', 'source', 'webpage']

  # Filter the dataset_json to include only the desired fields
  # filtered_dataset = {field: dataset_json['fields'][field] for field in desired_fields if
  #                     field in dataset_json['fields']}
  filtered_dataset = filter_and_order(dataset_json, desired_fields)

  # Include the model and pk in the filtered result if needed
  filtered_dataset['model'] = dataset_json['model']
  filtered_dataset['pk'] = dataset_json['pk']

  return filtered_dataset

# generate metadata for a collection
def collection_to_json(collid):
  coll = Collection.objects.get(id=collid)
  metadata_json = json.loads(serializers.serialize('json', [coll]))[0]  # Deserialize to get the first item

  # Define the fields you want to keep for collections
  collection_fields = ['title', 'creator', 'created', 'description', 'keywords', 'rel_keywords', 'numrows', 'webpage']
  dataset_fields = ['title', 'creator', 'create_date', 'description', 'numrows', 'source', 'webpage']

  # Filter the metadata_json to include only the desired fields
  # filtered_collection = {field: metadata_json['fields'][field] for field in desired_fields if
  #                        field in metadata_json['fields']}

  filtered_collection = filter_and_order(metadata_json, collection_fields)

  # If it's a dataset collection, include datasets with specified fields
  if coll.collection_class == 'dataset':
    filtered_collection['datasets'] = []
    for ds in coll.datasets.all():
      dataset_json = json.loads(serializers.serialize('json', [ds]))[0]
      # filtered_dataset = {field: dataset_json['fields'][field] for field in desired_fields if
      #                     field in dataset_json['fields']}
      filtered_dataset = filter_and_order(dataset_json, dataset_fields)

      # Append the filtered dataset
      filtered_collection['datasets'].append(filtered_dataset)

  # Include the model and pk in the filtered result if needed
  filtered_collection['model'] = metadata_json['model']
  filtered_collection['pk'] = metadata_json['pk']

  return filtered_collection

# build a .zip file with data file + README.txt
def create_zipfile(data_dump_filename, dsid=None, collid=None):
  today = makeNow()
  if dsid and not collid:
    # It's a single dataset
    metadata = dataset_to_json(dsid)
  elif collid:
    metadata = collection_to_json(collid)
    logger.debug('metadata_json_str', type(metadata), metadata)
    # return
  else:
    raise ValueError("Invalid parameters provided for zipfile creation.")

  pretty_metadata = json.dumps(metadata, indent=1, sort_keys=False)
  logger.debug('metadata_json', metadata)
  dl_class = "Dataset" if dsid else "Collection"
  # Create a README.txt file with the dataset JSON
  readme_content = (f'World Historical Gazetteer (WHG) \n{dl_class} Download\n'
                    f'data: {os.path.basename(data_dump_filename)}\n'
                    '********************************\n'
                    f'This dataset conforms to the CC-BY 4.0 NC license.\n\n'
                    "This license enables reusers to distribute, remix, adapt, and build upon the material "
                    "in any medium or format for noncommercial purposes only, and only so long as attribution "
                    "is given to the creator. CC BY-NC includes the following elements:\n"
                    "* Attribution — You must give appropriate credit, provide a link to the license, and indicate "
                    "if changes were made.\n"
                    "* NonCommercial — You may not use the material for commercial purposes.\n")
  readme_content += "\n***********************************\n"
  # for metadata_dict in metadata:
  #   logger.debug('metadata_dict', metadata_dict)
    # formatted_metadata = format_metadata(metadata_dict)
  readme_content += "\nMetadata:\n" + pretty_metadata

  # Write README.txt
  with open('README.txt', 'w') as f:
      f.write(readme_content)

  zipname = generate_zip_filename(data_dump_filename)

  # Create a .zip file that includes the README.txt file and the data dump
  with zipfile.ZipFile(zipname, 'w') as zipf:
    zipf.write('README.txt', arcname='README.txt')
    data_filename = os.path.basename(data_dump_filename)
    zipf.write(data_dump_filename, arcname=data_filename)

  # delete files - they  are in the zip now
  os.remove('README.txt')
  os.remove(data_dump_filename)

""" 
  called by utils.downloader()
  builds download .zip file for single dataset or entire collection
  in lpf or tsv, as requested/required
"""

@shared_task(name="make_download", bind=True)
def make_download(self, *args, **kwargs):
    logger.debug('make_download() args, kwargs: %s, %s', args, kwargs)
    
    try:
        user = User.objects.get(pk=kwargs['userid'])
    except User.DoesNotExist as e:
        logger.error('User with ID %s does not exist: %s', kwargs['userid'], e)
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'msg': 'User not found', 'error': str(e)}
    
    collid = kwargs.get('collid', None)
    dsid = kwargs.get('dsid', None)
    req_format = kwargs.get('format', 'json')  # Default to 'json' if format is not provided
    date = makeNow()
    
    try:
        if collid and not dsid:
            # Processing a collection
            coll = Collection.objects.get(id=collid)
            colltitle = coll.title
            collclass = coll.collection_class
            qs = coll.places_all.all()
            total_operations = qs.count()
            req_format = 'lpf'
            fn = 'media/downloads/'+str(user.id)+'_'+str(collid)+'_'+date+'.json'
            
            with open(fn, 'w', encoding='utf-8') as outfile:
                features = []
                for i, p in enumerate(qs):
                    try:
                        geoms = p.geoms.all()
                        if len(geoms) == 1:
                            geometry = geoms[0].jsonb
                        else:
                            geometry = {
                                "type": "GeometryCollection",
                                "geometries": [g.jsonb for g in geoms]
                            }
                        
                        try:
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
                            }
                        except Exception as e:
                            annotation = {}
                            logger.debug('Error fetching annotation or sequence for place %s: %s', p.id, e)
                        
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
                            "links": [ln.jsonb for ln in p.links.all()],
                            "whens": [w.jsonb for w in p.whens.all()]
                        }
                        features.append(rec)
                        
                        if (i + 1) % 100 == 0:
                            self.update_state(state='PROGRESS',
                                              meta={'current': i + 1, 'total': total_operations})
                            logger.debug('Task state: PROGRESS, current: %d, total: %d', i + 1, total_operations)
                    
                    except Exception as e:
                        logger.error('Error processing place %s: %s', p.id, e)
                        continue
                
                features_sorted = sorted(features, key=lambda x: x['properties']['annotation'].get('sequence', float('inf')))
                result = {
                    "type": "FeatureCollection",
                    "features": features_sorted,
                    "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
                    "filename": "/" + fn
                }
                outfile.write(json.dumps(result, indent=2).replace('null', '""'))
            
            create_zipfile(fn, None, collid)
            zipname = generate_zip_filename(fn)
            create_downloadfile_record(user, None, coll, zipname)
        
        elif dsid:
            # Processing a single dataset
            if collid:
                logger.debug('Single dataset in collection: %s, %s', dsid, collid)
            else:
                logger.debug('Solo dataset: %s', dsid)
            
            ds = Dataset.objects.get(pk=dsid)
            dslabel = ds.label
            qs = ds.places.all()
            total_operations = qs.count()
            logger.debug('Processing dataset: %s', dsid)
            
            if ds.format == 'delimited' and req_format in ['tsv', 'delimited']:
                try:
                    dsf = ds.file
                    df = pd.read_csv('media/'+dsf.file.name,
                                     delimiter=dsf.delimiter,
                                     engine='python',
                                     dtype={'id':'str','aat_types':'str'})
                    logger.debug('DataFrame loaded successfully')
                    
                    header = list(df)
                    newheader = list(set(header + ['lon', 'lat', 'matches', 'geo_id', 'geo_source', 'geowkt']))
                    
                    fn = 'media/downloads/'+str(user.id)+'_'+dslabel+'_'+date+'.tsv'
                    with open(fn, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile, delimiter='\t', quotechar='', quoting=csv.QUOTE_NONE)
                        writer.writerow(newheader)
                        missing = list(set(newheader) - set(header))
                        logger.debug('Missing columns: %s', missing)
                        
                        for i, row in df.iterrows():
                            try:
                                dfrow = df.loc[i, :]
                                p = qs.get(src_id=dfrow['id'], dataset=ds.label)
                                rowjs = json.loads(dfrow.to_json())
                                newrow = deepcopy(rowjs)
                                
                                for m in missing:
                                    newrow[m] = ''
                                
                                links = ';'.join(list(set([ln.jsonb['identifier'] for ln in p.links.all()])))
                                newrow['matches'] = links
                                
                                geoms = p.geoms.all()
                                if geoms.count() > 0:
                                    geowkt = newrow.get('geowkt', None)
                                    lonlat = [newrow.get('lon'), newrow.get('lat')]
                                    if not geowkt and (not lonlat or None in lonlat or lonlat[0] == ''):
                                        g = geoms[0]
                                        newrow['geowkt'] = g.geom.wkt if g.geom else ''
                                        xy = g.geom.coords[0] if g.jsonb['type'] == 'MultiPoint' else g.geom.coords
                                        newrow['lon'] = xy[0]
                                        newrow['lat'] = xy[1]
                                
                                index_map = {v: i for i, v in enumerate(newheader)}
                                ordered_row = sorted(newrow.items(), key=lambda pair: index_map[pair[0]])
                                csvrow = [o[1] for o in ordered_row]
                                writer.writerow(csvrow)
                                
                                if (i + 1) % 100 == 0:
                                    self.update_state(state='PROGRESS',
                                                      meta={'current': i + 1, 'total': total_operations})
                                    logger.debug('Task state: PROGRESS, current: %d, total: %d', i + 1, total_operations)
                                
                            except Exception as e:
                                logger.error('Error processing row %d: %s', i, e)
                                continue
                    
                    create_zipfile(fn, ds.id, None)
                    zipname = generate_zip_filename(fn)
                    create_downloadfile_record(user, ds, None, zipname)
                
                except Exception as e:
                    logger.error('Error processing dataset: %s', e)
                    self.update_state(state='FAILURE', meta={'error': str(e)})
                    return {'msg': 'Error processing dataset', 'error': str(e)}
            
            else:
                try:
                    fn = 'media/downloads/'+str(user.id)+'_'+dslabel+'_'+date+'.json'
                    with open(fn, 'w', encoding='utf-8') as outfile:
                        features = []
                        for i, p in enumerate(qs):
                            try:
                                whens = p.whens.all()
                                when = p.whens.first().jsonb if len(whens) > 0 else {}
                                geoms = p.geoms.all()
                                if len(geoms) == 1:
                                    geometry = geoms[0].jsonb
                                else:
                                    geometry = {
                                        "type": "GeometryCollection",
                                        "geometries": [g.jsonb for g in geoms]
                                    }
                                rec = {
                                    "type": "Feature",
                                    "@id": ds.uri_base + (str(p.id) if 'whgazetteer' in ds.uri_base else p.src_id),
                                    "properties": {
                                        "pid": p.id,
                                        "src_id": p.src_id,
                                        "title": p.title,
                                        "ccodes": p.ccodes
                                    },
                                    "geometry": geometry,
                                    "names": [n.jsonb for n in p.names.all()],
                                    "types": [t.jsonb for t in p.types.all()],
                                    "links": [ln.jsonb for ln in p.links.all()],
                                    "when": when
                                }
                                features.append(rec)
                                
                                if (i + 1) % 100 == 0:
                                    self.update_state(state='PROGRESS',
                                                      meta={'current': i + 1, 'total': total_operations})
                                    logger.debug('Task state: PROGRESS, current: %d, total: %d', i + 1, total_operations)
                            
                            except Exception as e:
                                logger.error('Error processing place %d: %s', p.id, e)
                                continue
                        
                        result = {
                            "type": "FeatureCollection",
                            "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
                            "filename": "/" + fn,
                            "description": ds.description,
                            "features": features
                        }
                        outfile.write(json.dumps(result, indent=2).replace('null', '""'))
                    
                    create_zipfile(fn, ds.id, None)
                    zipname = generate_zip_filename(fn)
                    create_downloadfile_record(user, ds, None, zipname)
                
                except Exception as e:
                    logger.error('Error processing dataset in LPF format: %s', e)
                    self.update_state(state='FAILURE', meta={'error': str(e)})
                    return {'msg': 'Error processing dataset in LPF format', 'error': str(e)}
    
    except Exception as e:
        logger.error('General error in make_download: %s', e)
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'msg': 'Error processing download', 'error': str(e)}
    
    logger.debug('@ Log create: user_id: %d, dsid: %s, collid: %s', user.id, dsid, collid)
    
    Log.objects.create(
        category='dataset' if dsid else 'collection',
        logtype='ds_download' if dsid else 'coll_download',
        note={"format": req_format, "name": user.username},
        dataset_id=dsid or None,
        collection_id=collid or None,
        user_id=user.id
    )
    
    try:
        new_emailer(
            email_type='download_ready',
            subject='WHG download file is ready',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_email=[user.email],
            name=user.username,
            greeting_name=user.name if user.name else user.username,
            label=ds.label if dsid else coll.title,
            title=ds.title if dsid else coll.title,
            email=user.email,
            taskname='Download',
        )
    except Exception as e:
        logger.error('Error sending download ready email: %s', e)
    
    self.update_state(state='SUCCESS')
    logger.debug('Task state: SUCCESS')
    
    completed_message = {"msg": req_format + " written", "filename": fn}
    return completed_message
