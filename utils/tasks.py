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
from collection.models import Collection
from datasets.models import Dataset
from datasets.utils import makeNow
from main.models import DownloadFile, Log
from places.models import Place

logger = get_task_logger(__name__)
es = settings.ES_CONN
User = get_user_model()

"""
  initiate make_download for datasets and collections
  called from download modals, ds_metadata.html
"""
def downloader(request, *args, **kwargs):
  print('downloader() user, request.POST', request.user, request.POST)
  dsid = request.POST.get('dsid') or None
  collid = request.POST.get('collid') or None
  user = request.user
  # POST *should* be the only case...
  if request.method == 'POST' and request.accepts('XMLHttpRequest'):
    print('ajax == True')
    format=request.POST['format']

    userid = request.user.id if request.user.is_authenticated else 1
    download_task = make_download.delay(
      userid=user.id,
      username=user.username,
      dsid=dsid or None,
      collid=collid or None,
      format=format or None
    )

    print('task to Celery', download_task.task_id)
    # return task_id
    obj={'task_id': download_task.task_id}
    print('obj from downloader()', obj)

    return HttpResponse(json.dumps(obj), content_type='application/json')

  elif request.method == 'POST' and not request.is_ajax:
    print('request.POST (not ajax)', request.POST)


  elif request.method == 'GET':
    print('request.GET', request.GET)

def generate_zip_filename(data_dump_filename):
    base_name, _ = os.path.splitext(data_dump_filename)
    zipname = base_name + '.zip'
    return zipname

"""
  create a DownloadFile record
"""
def create_downloadfile_record(user, ds, coll, zip_filename):
  # Determine the title based on whether it's a Collection or Dataset
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

def format_metadata(metadata_dict):
  formatted_lines = []
  for key, value in metadata_dict.items():
    formatted_line = f"{key}: {value}"
    formatted_lines.append(formatted_line)
  return "\n".join(formatted_lines)

# return ordered dict of metadata fields
def filter_and_order(metadata_json, desired_fields):
  # Directly using dict as Python 3.7+ maintains order
  filtered = {field: metadata_json['fields'][field] for field in desired_fields if field in metadata_json['fields']}
  return filtered

"""
  generate metadata for a single dataset
"""
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

"""
  generate metadata for a collection
"""
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

"""
  helper for make_download()
  build a .zip file with download file + README.txt
"""
def create_zipfile(data_dump_filename, dsid=None, collid=None):
  if dsid and not collid:
    # It's a single dataset
    metadata = dataset_to_json(dsid)
  elif collid:
    metadata = collection_to_json(collid)
    print('metadata_json_str', type(metadata), metadata)
    # return
  else:
    raise ValueError("Invalid parameters provided for zipfile creation.")

  pretty_metadata = json.dumps(metadata, indent=1, sort_keys=False)
  print('metadata_json', metadata)
  dl_class = "Dataset" if dsid else "Collection"
  # Create a README.txt file with the dataset JSON
  readme_content = (f'World Historical Gazetteer (WHG) \n{dl_class} Download\n'
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
  #   print('metadata_dict', metadata_dict)
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

  # Remember to delete the README.txt file if it's not needed anymore
  os.remove('README.txt')

# data_dump_filename = 'media/downloads/2_tm200_20240214_110011.json'
# dsid = 9
# from django.core import serializers
# create_zipfile(data_dump_filename, 9, None) # dataset
# create_zipfile(data_dump_filename, None, 6) # place collection

""" 
  called by utils.downloader()
  builds download file for single dataset or entire collection
  TODO: list usages
"""
@shared_task(name="make_download", bind=True)
def make_download(self, *args, **kwargs):
  print('make_download() args, kwargs', args, kwargs)
  user = User.objects.get(pk=kwargs['userid'])
  collid = kwargs['collid'] or None
  dsid = kwargs['dsid'] or None
  req_format = kwargs['format']
  print('make_download() userid, dsid, collid, format',
        user.id, dsid, collid, req_format)
  date = makeNow()

  # collection or dataset
  if collid and not dsid:
    # it's an entire collection; all places in all its datasets
    print('entire collection', collid)
    coll = Collection.objects.get(id=collid)
    colltitle = coll.title
    qs = coll.places_all.all()

    # count for progress
    total_operations = qs.count()

    # ensure format is lpf
    req_format = 'lpf'

    # name and open file for writing
    fn = 'media/downloads/'+str(user.id)+'_'+str(collid)+'_'+date+'.json'
    outfile= open(fn, 'w', encoding='utf-8')

    # build features list
    features = []
    for i, p in enumerate(qs):
      geoms = p.geoms.all()
      if len(geoms) == 1:
        geometry = geoms[0].jsonb
      else:
        geometry = {
          "type": "GeometryCollection",
          "geometries": [g.jsonb for g in geoms]
        }
      rec = {"type": "Feature",
             "properties": {"id": p.id, "src_id": p.src_id, "title": p.title, "ccodes": p.ccodes},
             "geometry": geometry,
             "names": [n.jsonb for n in p.names.all()],
             "types": [t.jsonb for t in p.types.all()],
             "links": [ln.jsonb for ln in p.links.all()],
             "whens": [w.jsonb for w in p.whens.all()],
      }
      features.append(rec)
      # update task state every 100 iterations
      if (i + 1) % 100 == 0:
        self.update_state(state='PROGRESS',
                                  meta={'current': i + 1, 'total': total_operations})
        print(f"Task state: PROGRESS, current: {i + 1}, total: {total_operations}")

    print(f'download file for {total_operations} places in {colltitle}')
    result = {"type": "FeatureCollection", "features": features,
              "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
              "filename": "/" + fn}

    # TODO: build zip file with README.txt
    create_downloadfile_record(user, None, coll, fn)

    outfile.write(json.dumps(result,indent=2).replace('null', '""'))

  elif dsid:
    # it's a single dataset
    if collid:
      print('single dataset in collection', dsid, collid)
    else:
      print('solo dataset', dsid)
    ds=Dataset.objects.get(pk=dsid)
    dslabel = ds.label
    qs = ds.places.all()

    # count for progress
    total_operations = qs.count()

    print("tasks.make_download()", {"format": req_format, "ds": dsid})

    if ds.format == 'delimited' and req_format in ['tsv', 'delimited']:
      print('making an augmented tsv file')

      # get header as uploaded and create newheader w/any "missing" columns
      # get latest dataset file
      dsf = ds.file
      # make pandas dataframe
      df = pd.read_csv('media/'+dsf.file.name,
                       delimiter=dsf.delimiter,
                       # delimiter='\t',
                       dtype={'id':'str','aat_types':'str'})
      print('df', df)
      # copy existing header to newheader for write
      header = list(df)
      # header = list(df)[0].split(',')
      newheader = deepcopy(header)

      # all exports should have these, empty or not
      newheader = list(set(newheader+['lon','lat','matches','geo_id','geo_source','geowkt']))

      # name and open csv file for writer
      fn = 'media/downloads/'+str(user.id)+'_'+dslabel+'_'+date+'.tsv'
      csvfile = open(fn, 'w', newline='', encoding='utf-8')
      writer = csv.writer(csvfile, delimiter='\t', quotechar='', quoting=csv.QUOTE_NONE)

      # TODO: better order?
      writer.writerow(newheader)
      # missing columns (were added to newheader)
      missing=list(set(newheader)-set(list(df)))
      print('missing',missing)

      for i, row in df.iterrows():
        dfrow = df.loc[i,:]
        # get db record
        # src_id is NOT distinct amongst all places!!
        p = qs.get(src_id = dfrow['id'], dataset = ds.label)

        # df row to newrow json object
        rowjs = json.loads(dfrow.to_json())
        newrow = deepcopy(rowjs)

        # add missing keys from newheader, if any
        for m in missing:
          newrow[m] = ''
        # newrow now has all keys -> fill with db values as req.

        # LINKS (matches)
        # get all distinct matches in db as string
        links = ';'.join(list(set([ln.jsonb['identifier'] for ln in p.links.all()])))
        # replace whatever was in file
        newrow['matches'] = links

        # GEOMETRY
        # if db has >0 geom and row has none, add lon/lat and geowkt
        # otherwise, don't bother
        geoms = p.geoms.all()
        if geoms.count() > 0:
          geowkt= newrow['geowkt'] if 'geowkt' in newrow else None

          lonlat= [newrow['lon'],newrow['lat']] if \
            len(set(newrow.keys())&set(['lon','lat']))==2 else None
          # lon/lat may be empty
          if not geowkt and (not lonlat or None in lonlat or lonlat[0]==''):
            # get first db geometry & add to newrow dict
            g=geoms[0]
            #newheader.extend(['geowkt'])
            newrow['geowkt']=g.geom.wkt if g.geom else ''
            # there is always jsonb
            # xy = g.geom.coords[0] if g.jsonb['type'] == 'MultiPoint' else g.geom.coords
            xy = g.geom.coords[0] if g.jsonb['type'] == 'MultiPoint' else g.jsonb['coordinates']
            newrow['lon'] = xy[0]
            newrow['lat'] = xy[1]
        #print(newrow)

        # match newrow order to newheader already written
        index_map = {v: i for i, v in enumerate(newheader)}
        ordered_row = sorted(newrow.items(), key=lambda pair: index_map[pair[0]])

        # write it
        csvrow = [o[1] for o in ordered_row]
        writer.writerow(csvrow)

        if (i + 1) % 100 == 0:  # Update state every 100 iterations
          try:
            self.update_state(state='PROGRESS',
                                      meta={'current': i + 1, 'total': total_operations})
            print(f"Task state: PROGRESS, current: {i + 1}, total: {total_operations}")

            task_id = self.request.id
            task_result = AsyncResult(task_id)
            print(f"Immediate task state: {task_result.state}, info: {task_result.info}")
          except Exception as e:
            print(f"Error updating task state: {e}")

      csvfile.close()
      create_zipfile(ds, fn) # single dataset
      zipname = generate_zip_filename(fn)
      create_downloadfile_record(user, ds, None, zipname)

    else:
      print('building lpf file')
      # make file name
      fn = 'media/downloads/'+str(user.id)+'_'+dslabel+'_'+date+'.json'
      # open file for writing
      outfile = open(fn, 'w', encoding='utf-8')

      # build features list
      features = []
      for i, p in enumerate(qs):
        when = p.whens.first().jsonb
        if 'minmax' in when:
          del when['minmax']
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
          "properties": {"pid": p.id, "src_id": p.src_id, "title": p.title, "ccodes": p.ccodes},
          "geometry": geometry,
          "names": [n.jsonb for n in p.names.all()],
          "types": [t.jsonb for t in p.types.all()],
          "links": [ln.jsonb for ln in p.links.all()],
          "when": when
        }
        features.append(rec)
        # update task state every 100 iterations
        if (i + 1) % 100 == 0:
          self.update_state(state='PROGRESS',
                                    meta={'current': i + 1, 'total': total_operations})
          print(f"Task updated: current iteration is {i + 1}, total operations are {total_operations}")

      print('download file for ' + str(total_operations) + ' places')

      result={"type":"FeatureCollection",
              "@context": "https://raw.githubusercontent.com/LinkedPasts/linked-places/master/linkedplaces-context-v1.1.jsonld",
              "filename": "/"+fn,
              "decription": ds.description,
              "features":features}

      create_downloadfile_record(user, ds, None, fn)

      outfile.write(json.dumps(result, indent=2).replace('null', '""'))
      # TODO: build zip file with README.txt

  # log the download, dataset or collection
  Log.objects.create(
    # category, logtype, "timestamp", subtype, note, dataset_id, collection_id, user_id
    category = 'dataset' if dsid else 'collection',
    logtype = 'ds_download' if dsid else 'coll_download',
    note = {"format": req_format, "name": user.username},
    dataset_id = dsid or None,
    collection_id = collid or None,
    user_id = user.id
  )

  from utils.emailing import new_emailer
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

  self.update_state(state='SUCCESS')
  print("Task state: SUCCESS")
  # for ajax, just report filename
  # completed_message = {"msg": req_format+" written", "filename": fn, "rows": count}
  completed_message = {"msg": req_format+" written", "filename": fn}
  return completed_message
