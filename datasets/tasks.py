# celery tasks for reconciliation and downloads
# align_tgn(), align_wdlocal(), align_idx(), align_whg, make_download
from __future__ import absolute_import, unicode_literals
from django_celery_results.models import TaskResult
from django.conf import settings
from django.core import serializers
from django.db import transaction, connection
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from celery import shared_task
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
import codecs, csv, datetime, itertools, os, re, sys, zipfile
from copy import deepcopy
from elasticsearch8.helpers import streaming_bulk
from itertools import chain
import pandas as pd
import simplejson as json

from areas.models import Area
from collection.models import Collection
from datasets.models import Dataset, Hit
from datasets.static.hashes.parents import ccodes as cchash
from datasets.static.hashes.qtypes import qtypes
from elastic.es_utils import makeDoc, build_qobj, profileHit
from datasets.utils import elapsed, getQ, \
  HitRecord, hully, parse_wkt, post_recon_update #  bestParent, makeNow,
from main.models import Log, DownloadFile
from places.models import Place

logger = get_task_logger(__name__)
es = settings.ES_CONN
User = get_user_model()

"""
  adds newly public dataset to 'pub' index
  making it accessible to search (and API eventually)
"""
@shared_task()
def index_to_pub(dataset_id, idx='pub'):
    es = settings.ES_CONN
    # Fetch dataset by ID
    try:
        dataset = Dataset.objects.get(pk=dataset_id, ds_status__in=['wd-complete', 'accessioning'])
    except Dataset.DoesNotExist:
        print(f"Dataset with ID {dataset_id} does not exist or is not public/ready for accessioning.")
        return  # Exit if dataset conditions aren't met

    print(f"Indexing dataset {dataset_id} to 'pub' index...")
    places_to_index = Place.objects.filter(dataset=dataset, indexed=False, idx_pub=False)
    place_ids_to_index = list(places_to_index.values_list('id', flat=True))

    # convert a Place into a dict that's ready for indexing
    def make_bulk_doc(place):
        doc = makeDoc(place)
        doc['whg_id'] = ''
        # Add names and title to search field
        searchy_content = set(doc.get('searchy', []))
        searchy_content.update(n['toponym'] for n in doc['names'])
        searchy_content.add(doc['title'])
        doc['searchy'] = list(searchy_content)
        return {
            "_index": idx,
            "_id": place.id,  # place ID as document ID
            "_source": doc,
        }

    actions = (make_bulk_doc(place) for place in places_to_index.iterator())

    # Perform the bulk index operation and collect the response
    successes, failed_docs = 0, []
    with transaction.atomic():  # Use a transaction to prevent race conditions
        for ok, action in streaming_bulk(es, actions, index=idx, raise_on_error=False):
            if ok:
                successes += 1
            else:
                failed_docs.append(action)

    # Update the idx_pub flag for all successful Place objects using the Place IDs
    Place.objects.filter(id__in=place_ids_to_index).update(idx_pub=True)

    print(f"Indexing complete. Total indexed places: {successes}. Failed documents: {len(failed_docs)}")
    if failed_docs:
        print(f"Failed documents: {failed_docs}")

"""
  unindex from 'pub': an entire dataset or a single record
"""
@shared_task()
def unindex_from_pub(dataset_id=None, place_id=None, idx='pub'):
  es = settings.ES_CONN
  if place_id:
    try:
      # Check if the place exists and is indexed in 'pub'
      place = Place.objects.get(pk=place_id, idx_pub=True)
      # Perform the delete operation for the specific place
      response = es.delete(index=idx, id=str(place_id), refresh=True)
      # Check if delete operation was successful
      if response.get('result') != 'deleted':
        raise Exception("Elasticsearch delete operation failed")
      else:
        print('pub record deleted in unindex_from_pub():', place)
      # Update the idx_pub flag for this Place object
      place.idx_pub = False
      place.save()
    except Place.DoesNotExist:
      logger.error(f"Place with ID {place_id} does not exist or is not indexed to 'pub'.")
    except Exception as e:
      logger.error(f"An error occurred while attempting to unindex place with ID {place_id}: {e}")
      raise  # Re-raise exception to ensure it's caught by Celery
    return {'place_id': place_id}

  elif dataset_id:
    try:
      dataset = Dataset.objects.get(pk=dataset_id)
    except Dataset.DoesNotExist:
      print(f"Dataset with ID {dataset_id} does not exist.")
      return  # Exit if the dataset is not found

    # query for es.delete_by_query
    query = {
      "query": {
        "term": {
          "dataset": dataset.label  # This field should match the field in the ES document
        }
      }
    }

    # Perform the delete_by_query operation
    response = es.delete_by_query(index=idx, body=query, refresh=True)

    # Check for failures and take necessary actions
    if response['failures']:
      print(f"Failures in unindexing: {response['failures']}")

    # Now, update the idx_pub flag for all Place objects of this dataset
    with transaction.atomic():
      Place.objects.filter(dataset=dataset).update(idx_pub=False)

    place_ids = Place.objects.filter(dataset_id=dataset_id, idx_pub=True).values_list('id', flat=True)
    return {'place_ids': list(place_ids)}

  print(f"Unindexing complete")

# test task for uptimerobot
@shared_task(name="testAdd")
def testAdd(n1,n2):
  sum = n1+n2
  return sum

def types(hit):
  type_array = []
  for t in hit["_source"]['types']:
    if bool(t['placetype'] != None):
      type_array.append(t['placetype']+', '+str(t['display']))
  return type_array

def names(hit):
  name_array = []
  for t in hit["_source"]['names']:
    if bool(t['name'] != None):
      name_array.append(t['name']+', '+str(t['display']))
  return name_array

def toGeoJSON(hit):
  src = hit['_source']
  feat = {"type": "Feature", "geometry": src['location'],
            "aatid": hit['_id'], "tgnid": src['tgnid'],
            "properties": {"title": src['title'], "parents": src['parents'], "names": names(hit), "types": types(hit) } }
  return feat

def reverse(coords):
  fubar = [coords[1],coords[0]]
  return fubar

def maxID(es,idx):
  q={"query": {"bool": {"must" : {"match_all" : {}} }},
       "sort": [{"whg_id": {"order": "desc"}}],
       "size": 1  
       }
  try:
    res = es.search(index=idx, body=q)
    maxy = int(res['hits']['hits'][0]['_source']['whg_id'])
  except:
      maxy = 12345677
  return maxy 

def parseDateTime(string):
  year = re.search("(\d{4})-",string).group(1)
  if string[0] == '-':
    year = year + ' BCE' 
  return year.lstrip('0')

def ccDecode(codes):
  countries=[]
  #print('codes in ccDecode',codes)
  for c in codes:
    countries.append(cchash[0][c]['gnlabel'])
  return countries
  
# generate an appropriate title, language-dependent {name} ({en}) in the case of wikidata
def make_title(h, lang):
  if 'dataset' in h and h['dataset'] == 'geonames':
    title = h['variants']['names'][0]
  elif len(h['variants']) == 0:
    title = 'unnamed'
  else:
    vl_en = next((v for v in h['variants'] if v['lang'] == 'en'), None)
    vl_pref = next((v for v in h['variants'] if v['lang'] == lang), None)
    vl_first = next((v for v in h['variants']), None)

    title = vl_pref['names'][0] + (' (' + vl_en['names'][0] + ')' if vl_en else '') \
      if vl_pref and lang != 'en' else vl_en['names'][0] if vl_en else vl_first['names'][0]
  return title
  # if len(variants) == 0:
  #   return 'unnamed'
  # else:
  #   vl_en=next( (v for v in variants if v['lang'] == 'en'), None)#; print(vl_en)
  #   vl_pref=next( (v for v in variants if v['lang'] == lang), None)#; print(vl_pref)
  #   vl_first=next( (v for v in variants ), None); print(vl_first)
  #
  #   title = vl_pref['names'][0] + (' (' + vl_en['names'][0] + ')' if vl_en else '') \
  #     if vl_pref and lang != 'en' else vl_en['names'][0] if vl_en else vl_first['names'][0]
  #   return title

def wdDescriptions(descrips, lang):
  dpref=next( (v for v in descrips if v['lang'] == lang), None)
  dstd=next( (v for v in descrips if v['lang'] == 'en'), None)

  result = [dstd, dpref] if lang != 'en' else [dstd] \
    if dstd else []
  return result

# create cluster payload from set of hits for a place
def normalize_whg(hits):
  result = []
  src = [h['_source'] for h in hits]
  parents = [h for h in hits if 'whg_id' in h['_source']]
  children = [h for h in hits if 'whg_id' not in h['_source']]
  titles=list(set([h['_source']['title'] for h in hits]))
  [links, countries] = [[],[]]
  for h in src:
    countries.append(ccDecode(h['ccodes']))
    for l in h['links']:
      links.append(l['identifier'])
  # each parent seeds cluster of >=1 hit
  for par in parents:
    kid_ids = par['_source']['children'] or None
    kids = [c['_source'] for c in children if c['_id'] in kid_ids]
    cluster={
      "whg_id": par["_id"],
      "titles": titles,
      "countries":list(set(countries)), 
      "links":list(set(links)), 
      "geoms":[],
      "sources":[]
    }
    result.append(cluster)
  return result.toJSON()
    
    
# normalize hit json from any authority
# language relevant only for wikidata local)
def normalize(h, auth, language=None):
  print('auth in normalize', auth)
  rec = None
  if auth.startswith('whg'):
    # for whg h is full hit, not only _source
    hit = deepcopy(h)
    h = hit['_source']
    #_id = hit['_id']
    # build a json object, for Hit.json field
    rec = HitRecord(
      h['place_id'], 
      h['dataset'],
      h['src_id'], 
      h['title']
    )
    #print('"rec" HitRecord',rec)
    rec.score = hit['_score']
    rec.passnum = hit['pass'][:5]
    
    # only parents have whg_id
    if 'whg_id' in h:
      rec.whg_id = h['whg_id']
    
    # add elements if non-empty in index record
    rec.variants = [n['toponym'] for n in h['names']] # always >=1 names
    # TODO: fix grungy hack (index has both src_label and sourceLabel)
    key = 'src_label' if 'src_label' in h['types'][0] else 'sourceLabel'      
    rec.types = [t['label']+' ('+t[key]  +')' if t['label']!=None else t[key] \
                for t in h['types']] if len(h['types']) > 0 else []
    # TODO: rewrite ccDecode to handle all conditions coming from index
    # ccodes might be [] or [''] or ['ZZ', ...]
    rec.countries = ccDecode(h['ccodes']) if ('ccodes' in h.keys() and (len(h['ccodes']) > 0 and h['ccodes'][0] !='')) else []
    # rec.parents = ['partOf: '+r.label+' ('+parseWhen(r['when']['timespans'])+')' for r in h['relations']] \
    # TODO: what happened to parseWhen()?
    rec.parents = ['partOf: '+r.label+' ('+r['when']['timespans']+')' for r in h['relations']] \
                if 'relations' in h.keys() and len(h['relations']) > 0 else []
    rec.descriptions = h['descriptions'] if len(h['descriptions']) > 0 else []
    
    rec.geoms = [{
      "type":h['geoms'][0]['location']['type'],
      "coordinates":h['geoms'][0]['location']['coordinates'],
      "id":h['place_id'],
        "ds":"whg"}] \
      if len(h['geoms'])>0 else []   
    
    rec.minmax = dict(sorted(h['minmax'].items(),reverse=True)) if len(h['minmax']) > 0 else []
    
    # TODO: deal with whens
    #rec.whens = [parseWhen(t) for t in h['timespans']] \
                #if len(h['timespans']) > 0 else []
    rec.links = [l['identifier'] for l in h['links']] \
                if len(h['links']) > 0 else []    
  elif auth == 'wd':
    try:
      # locations and links may be multiple, comma-delimited
      locs=[]; links = []
      if 'locations' in h.keys():
        for l in h['locations']['value'].split(', '):
          loc = parse_wkt(l)
          loc["id"]=h['place']['value'][31:]
          loc['ds']='wd'
          locs.append(loc)
      #if 'links' in h.keys():
        #for l in h['links']:
          #links.append('closeMatch: '+l)
      #  place_id, dataset, src_id, title
      rec = HitRecord(-1, 'wd', h['place']['value'][31:], h['placeLabel']['value'])
      #print('"rec" HitRecord',rec)      
      rec.variants = []
      rec.types = h['types']['value'] if 'types' in h.keys() else []
      rec.ccodes = [h['countryLabel']['value']]
      rec.parents =h['parents']['value'] if 'parents' in h.keys() else []
      rec.geoms = locs if len(locs)>0 else []
      rec.links = links if len(links)>0 else []
      rec.minmax = []
      rec.inception = parseDateTime(h['inception']['value']) if 'inception' in h.keys() else ''
      rec.dataset = h['dataset'] if 'dataset' in h.keys() else ''
    except:
      print("normalize(wd) error:", h['place']['value'][31:], sys.exc_info())    
  elif auth == 'wdlocal':
    # hit['_source'] keys() for dataset='wikidata': ['types', 'authids', 'claims', 'fclasses',
    # 'sitelinks', 'location', 'id', 'variants', 'type', 'descriptions', 'dataset', 'repr_point'])
    # hit['_source'] keys() for dataset='geonames': ['id', 'fclasses', 'location', 'repr_point', 'variants', 'dataset']
    try:
      print('h in normalize', h)
      # which index is the target?
      is_wdgn = 'dataset' in h.keys()
      print('is_wdgn?', is_wdgn)
      dataset = h['dataset'] if is_wdgn else 'wd'
      print('dataset', dataset)
      variants = h['variants']
      fclasses = h['fclasses']
      title = make_title(h, language)

      # create base HitRecord(place_id, dataset, auth_id, title
      rec = HitRecord(-1, dataset, h['id'], title)

      # build variants array per dataset
      if is_wdgn and h['dataset'] == 'geonames':
        rec.variants = variants['names']
        rec.fclasses = fclasses
      else:  # wikidata
        v_array=[]
        for v in variants:
          # if not is_wdgn:
          for n in v['names']:
            if n != title:
              v_array.append(n+'@'+v['lang'])
        rec.variants = v_array
            
      if 'location' in h.keys():
        # single MultiPoint geometry
        loc = h['location']
        print('location IS in hit', loc)
        loc['id'] = h['id']
        loc['ds'] = dataset
        # single MultiPoint geom if exists
        rec.geoms = [loc]
      else:
        print('no location in hit', h)

      # if not is_wdgn: # it's wd
      if dataset != 'geonames':   # it's wd or wikidata
        rec.links = h['authids']

        # look up Q class labels
        htypes = set(h['claims']['P31'])
        qtypekeys = set([t[0] for t in qtypes.items()])
        rec.types = [qtypes[t] for t in list(set(htypes & qtypekeys))]

        # countries
        rec.ccodes = [
          cchash[0][c]['gnlabel'] for c in cchash[0] \
            if cchash[0][c]['wdid'] in h['claims']['P17']
        ]

        # include en + native lang if not en
        rec.descriptions = wdDescriptions(h['descriptions'], language) if 'descriptions' in h.keys() else []

        # not applicable
        rec.parents = []

        # no minmax in hit if no inception value(s)
        rec.minmax = [h['minmax']['gte'],h['minmax']['lte']] if 'minmax' in h else []
    except Exception as e:
      print("normalize(wdlocal) error:", h['id'], str(e))
      print('Hit rec', rec)

  # elif auth == 'tgn':
  #   rec = HitRecord(-1, 'tgn', h['tgnid'], h['title'])
  #   rec.variants = [n['toponym'] for n in h['names']] # always >=1 names
  #   rec.types = [(t['placetype'] if 'placetype' in t and t['placetype'] != None else 'unspecified') + \
  #               (' ('+t['id']  +')' if 'id' in t and t['id'] != None else '') for t in h['types']] \
  #               if len(h['types']) > 0 else []
  #   rec.ccodes = []
  #   rec.parents = ' > '.join(h['parents']) if len(h['parents']) > 0 else []
  #   rec.descriptions = [h['note']] if h['note'] != None else []
  #   if 'location' in h.keys():
  #     rec.geoms = [{
  #       "type":"Point",
  #       "coordinates":h['location']['coordinates'],
  #       "id":h['tgnid'],
  #         "ds":"tgn"}]
  #   else:
  #     rec.geoms=[]
  #   rec.minmax = []
  #   rec.links = []
    #print(rec)
  else:
    rec = HitRecord(-1, 'unknown', 'unknown', 'unknown')

  print('normalized hit record', rec.toJSON())
  return rec.toJSON()

# ***
# elasticsearch filter from Area (types: predefined, ccodes, drawn)
# e.g. {'type': ['drawn'], 'id': ['128']}
# called from: es_lookup_tgn(), es_lookup_idx(), es_lookup_wdlocal(), search.SearchView(), 
# FUTURE: parse multiple areas
# ***
# def get_bounds_filter(bounds, idx):
#   #print('bounds in get_bounds_filter()',bounds)
#   id = bounds['id'][0]
#   #areatype = bounds['type'][0]
#   area = Area.objects.get(id = id)
#   #
#   # geofield = "geoms.location" if idx == 'whg' else "location"
#   geofield = "geoms.location" if idx == 'whg' else "location"
#   filter = { "geo_shape": {
#     geofield: {
#         "shape": {
#           "type": area.geojson['type'],
#           "coordinates": area.geojson['coordinates']
#         },
#         "relation": "intersects" if idx=='whg' else 'within' # within | intersects | contains
#       }
#   }}
#   return filter

# accounts for GeometryCollection case
def get_bounds_filter(bounds, idx):
  id = bounds['id'][0]
  area = Area.objects.get(id=id)

  # Check if the geometry is a GeometryCollection
  if area.geojson['type'] == 'GeometryCollection':
    # Assuming the first geometry in the collection can be used for filtering
    first_geometry = area.geojson['geometries'][0]
    geo_type = first_geometry['type']
    coordinates = first_geometry['coordinates']
  else:
    geo_type = area.geojson['type']
    coordinates = area.geojson['coordinates']

  geofield = "geoms.location" if idx == 'whg' else "location"
  filter = {
    "geo_shape": {
      geofield: {
        "shape": {
          "type": geo_type,
          "coordinates": coordinates
        },
        "relation": "intersects" if idx == 'whg' else 'within'  # within | intersects | contains
      }
    }
  }
  return filter


"""
performs elasticsearch > wdlocal queries
from align_wdlocal()
"""
def es_lookup_wdlocal(qobj, *args, **kwargs):
  # idx = 'wd'
  idx = 'wdgn'  # wikidata + geonames

  #bounds object: {'type': ['userarea'], 'id': ['0']}
  bounds = kwargs['bounds']
  exclude_geonames = True if kwargs['geonames'] == 'on' else False
  print('kwargs in es_lookup_wdlocal()', kwargs)
  # print('exclude_geonames?', exclude_geonames)
  hit_count = 0

  # empty result object
  result_obj = {
    'place_id': qobj['place_id'], 
    'hits':[],'missed':-1, 'total_hits':-1}  

  # names (distinct, w/o language)
  variants = list(set(qobj['variants']))

  # types
  # wikidata Q ids for aat_ids, ccodes; strip wd: prefix
  # if no aatids, returns ['Q486972'] (human settlement)
  qtypes = [t[3:] for t in getQ(qobj['placetypes'],'types')]

  # prep spatial 
  
  # if no ccodes, returns []
  countries = [t[3:] for t in getQ(qobj['countries'],'ccodes')]
  
  has_bounds = bounds['id'] != ['0']
  has_geom = 'geom' in qobj.keys()
  has_countries = len(countries) > 0
  if has_bounds:
    print("Bounds filter is being added")
    area_filter = get_bounds_filter(bounds, 'wd')
  if has_geom:
    print("Geometric filter is being added")
    shape_filter = { "geo_shape": {
      "location": {
        "shape": {
          "type": qobj['geom']['type'],
          "coordinates" : qobj['geom']['coordinates']},
        "relation": "intersects" }
    }}
  if has_countries:
    countries_match = {"terms": {"claims.P17":countries}}
  
  # initial paass0 query: any authid matches?
  # can be auto accepted without review if desired
  # incoming qobj['authids'] might include
  # a wikidata identifier matching an index _id (Qnnnnnnn)
  # 2024-05-18: OR a geonames id match in the index "id" field
  # OR any id match in wikidata authids[] e.g. gn:, tgn:, pl:, bnf:, viaf:

  # 18 May 24: OR a geonames id match in authids[] e.g. gn:1234567
  q0 = {
    "query": {
      "bool": {
        "must": [
          {
            "bool": {
              "should": [
                {"terms": {"authids": qobj['authids']}},  # Existing match on authids
                {
                  "bool": {
                    "must": [
                      {"terms": {"_id": [i[3:] for i in qobj['authids'] if i.startswith("wd:")]}},
                      {"term": {"dataset": "wikidata"}}
                    ]
                  }
                },  # Match on wikidata IDs
                {
                  "bool": {
                    "must": [
                      {"terms": {"id": [i[3:] for i in qobj['authids'] if i.startswith("gn:")]}},
                      {"term": {"dataset": "geonames"}}
                    ]
                  }
                }  # Match on geonames IDs
              ],
              "minimum_should_match": 1
            }
          }
        ]
      }
    }
  }

  # q0 = {"query": {
  #   "bool": {
  #     "must": [
  #       {"bool": {
  #         "should": [
  #           {"terms": {"authids": qobj['authids']}},
  #           # capture any wd: Q ids
  #           {"terms": {"_id": [i[3:] for i in qobj['authids']] }}
  #         ],
  #         "minimum_should_match": 1
  #       }}
  #     ]
  # }}}

  # base query
  qbase = {"query": { 
    "bool": {
      "must": [
        {"terms": {"variants.names":variants}}
      ],
      # boosts score if matched
      "should":[
        {"terms": {"authids": qobj['authids']}}
      ],
      "filter": []
    }
  }}

  # If exclude_geonames is True, add a must_not condition
  if exclude_geonames:
    exclude_condition = {"term": {"dataset": "geonames"}}
    q0["query"]["bool"]["must_not"] = [exclude_condition]
    qbase["query"]["bool"]["must_not"] = [exclude_condition]

  print('q0',q0)
  print('qbase',qbase)


  # add spatial filter as available in qobj
  if has_geom:
    # shape_filter is polygon hull ~100km diameter
    qbase['query']['bool']['filter'].append(shape_filter)
    if has_countries:
      qbase['query']['bool']['should'].append(countries_match)
  elif has_countries:
    # matches ccodes
    qbase['query']['bool']['must'].append(countries_match)
  elif has_bounds:
    # area_filter (predefined region or study area)
    qbase['query']['bool']['filter'].append(area_filter)
    if has_countries:
      qbase['query']['bool']['should'].append(countries_match)

  
  # q1 = qbase + types
  q1 = deepcopy(qbase)
  q1['query']['bool']['must'].append(    
    {"terms": {"types.id":qtypes}})

  # add fclasses if any, drop types; geom if any remains
  q2 = deepcopy(qbase)
  if len(qobj['fclasses']) > 0:
    q2['query']['bool']['must'].append(
      {"terms": {"fclasses":qobj['fclasses']}})

  # /\/\/\/\/\/
  # pass0 (q0): 
  # must[authid]; match any link
  # /\/\/\/\/\/
  print("Attempting Elasticsearch query for q0")
  try:
    res0 = es.search(index=idx, body = q0)
    hits0 = res0['hits']['hits']
    print("Query result for q0:", hits0)
  except Exception as e:
    print("Error during q0 search:", str(e), qobj)

  if len(hits0) > 0:
    for hit in hits0:
      hit_count +=1
      hit['pass'] = 'pass0'
      result_obj['hits'].append(hit)
  elif len(hits0) == 0:
    #print('q0 (no hits)', qobj)
    # /\/\/\/\/\/
    # pass1 (q1): 
    # must[name, placetype]; spatial filter
    # /\/\/\/\/\/
    #print('q1',q1)
    try:
      res1 = es.search(index=idx, body = q1)
      hits1 = res1['hits']['hits']
    except:
      print('pass1 error qobj:', qobj, sys.exc_info())
      print('pass1 error q1:', q1)
      sys.exit()
    if len(hits1) > 0:
      for hit in hits1:
        hit_count +=1
        hit['pass'] = 'pass1'
        result_obj['hits'].append(hit)
    elif len(hits1) == 0:
      # /\/\/\/\/\/
      # pass2: remove type, add fclasses
      # /\/\/\/\/\/  
      #print('q1: no hits',q1)
      try:
        res2 = es.search(index=idx, body = q2)
        hits2 = res2['hits']['hits']
      except:
        print('pass2 error qobj', qobj, sys.exc_info())
        print('pass2 error q2', q2)
        sys.exit()
      if len(hits2) > 0:
        for hit in hits2:
          hit_count +=1
          hit['pass'] = 'pass2'
          result_obj['hits'].append(hit)
      elif len(hits2) == 0:
        result_obj['missed'] = str(qobj['place_id']) + ': ' + qobj['title']
        #print('q2: no hits',q2)
  result_obj['hit_count'] = hit_count
  return result_obj


"""
manage align/reconcile to local wikidata index
get result_obj per Place via es_lookup_wdlocal()
parse, write Hit records for review

"""
@shared_task(name="align_wdlocal")
def align_wdlocal(*args, **kwargs):
  print('align_wdlocal.request', align_wdlocal.request)
  print('kwargs from align_wdlocal() task', kwargs)

  task_id = align_wdlocal.request.id
  task_status = AsyncResult(task_id).status
  ds = get_object_or_404(Dataset, id=kwargs['ds'])
  user = get_object_or_404(User, pk=kwargs['user'])
  bounds = kwargs['bounds']
  scope = kwargs['scope']
  scope_geom = kwargs['scope_geom']
  geonames = kwargs['geonames'] # exclude? on/off
  language = kwargs['lang']

  hit_parade = {"summary": {}, "hits": []}
  [nohits,wdlocal_es_errors,features] = [[],[],[]]
  [count_hit, count_nohit, total_hits, count_p0, count_p1, count_p2] = [0,0,0,0,0,0]
  start = datetime.datetime.now()
  # there is no test option for wikidata, but needs default
  test = 'off'

  # queryset depends on 'scope'
  qs = ds.places.all() if scope == 'all' else \
    ds.places.filter(~Q(review_wd = 1))
  # TODO: scope_geom is not used presently
  if scope_geom == 'geom_free':
    qs = qs.filter(geoms__isnull=True)

  print('scope, count', scope, qs.count())
  for place in qs:
    # build query object
    qobj = {"place_id":place.id,
            "src_id":place.src_id,
            "title":place.title,
            "fclasses":place.fclasses or []}

    [variants,geoms,types,ccodes,parents,links]=[[],[],[],[],[],[]]

    # ccodes (2-letter iso codes)
    for c in place.ccodes:
      ccodes.append(c.upper())
    qobj['countries'] = place.ccodes

    # types (Getty AAT integer ids if available)
    for t in place.types.all():
      if t.jsonb['identifier'].startswith('aat:'):
        types.append(int(t.jsonb['identifier'].replace('aat:','')) )
    qobj['placetypes'] = types

    # variants
    variants.append(place.title)
    for name in place.names.all():
      variants.append(name.toponym)
    qobj['variants'] = list(set(variants))

    # parents
    if len(place.related.all()) > 0:
      for rel in place.related.all():
        if rel.jsonb['relationType'] == 'gvp:broaderPartitive':
          parents.append(rel.jsonb['label'])
      qobj['parents'] = parents
    else:
      qobj['parents'] = []

    # geoms
    if len(place.geoms.all()) > 0:
      g_list =[g.jsonb for g in place.geoms.all()]
      # make simple polygon hull for ES shape filter
      qobj['geom'] = hully(g_list)
      # make a representative_point
      #qobj['repr_point'] = pointy(g_list)
      

    # 'P1566':'gn', 'P1584':'pleiades', 'P244':'loc', 'P214':'viaf', 'P268':'bnf', 'P1667':'tgn',
    # 'P2503':'gov', 'P1871':'cerl', 'P227':'gnd'
    # links
    if len(place.links.all()) > 0:
      l_list = [l.jsonb['identifier'] for l in place.links.all()]
      qobj['authids'] = l_list
    else:
      qobj['authids'] = []
      
    # TODO: ??? skip records that already have a Wikidata record in l_list
    # they are returned as Pass 0 hits right now
    # run pass0-pass2 ES queries
    # in progress: lookup on wdgn index instead of wd
    result_obj = es_lookup_wdlocal(qobj, bounds=bounds, geonames=geonames)
      
    if result_obj['hit_count'] == 0:
      count_nohit +=1
      nohits.append(result_obj['missed'])
    else:
      # place/task status 0 (unreviewed hits)
      place.review_wd = 0
      place.save()

      count_hit +=1
      total_hits += len(result_obj['hits'])


      for hit in result_obj['hits']:
        hit_id = hit['_source']['id']
        print("pre-write hit['_source']", hit['_source'])
        if hit['pass'] == 'pass0': 
          count_p0+=1 
        if hit['pass'] == 'pass1': 
          count_p1+=1 
        elif hit['pass'] == 'pass2': 
          count_p2+=1
        hit_parade["hits"].append(hit)
        new = Hit(
          # authority = 'wd',
          authority = 'wikidata' if 'Q' in hit_id else 'geonames',
          authrecord_id = hit['_source']['id'],
          dataset = ds,
          place = place,
          task_id = task_id,
          query_pass = hit['pass'],
          # prepare for consistent display in review screen
          json = normalize(hit['_source'], 'wdlocal', language),
          src_id = qobj['src_id'],
          score = hit['_score'],
          reviewed = False,
          matched = False
        )
        new.save()
        # print('new hit in align_wdlocal', hit['_source'])
  end = datetime.datetime.now()

  print('wdlocal ES errors:',wdlocal_es_errors)
  hit_parade['summary'] = {
      'count':qs.count(),
      'got_hits':count_hit,
      'total_hits': total_hits, 
      'pass0': count_p0, 
      'pass1': count_p1, 
      'pass2': count_p2, 
      'no_hits': {'count': count_nohit },
      'elapsed': elapsed(end-start)
    }
  print("summary returned",hit_parade['summary'])

  # create log entry and update ds status
  post_recon_update(ds, user, 'wdlocal', test)

  # email owner when complete
  from utils.emailing import new_emailer
  new_emailer(
    email_type='align_wdlocal',
    subject='Wikidata alignment task complete',
    from_email=settings.DEFAULT_FROM_EMAIL,
    to_email=[user.email],
    name=user.username,
    greeting_name=user.name if user.name else user.username,
    dslabel=ds.label,
    dstitle=ds.title,
    email=user.email,
    # TODO: get correct counts for message
    counthit=count_hit,  # of records with any hit(s)
    totalhits=total_hits,  # of hits
    taskname='Wikidata',
    status=task_status,
  )

  return hit_parade['summary']


"""
# performs elasticsearch > whg index queries
# from align_idx(), returns result_obj

"""
def es_lookup_idx(qobj, *args, **kwargs):
  #print('kwargs from es_lookup_idx',kwargs)
  global whg_id
  idx = 'whg'
  bounds = kwargs['bounds']  # e.g. {'type': ['userarea'], 'id': ['0']}
  [hitobjlist, _ids] = [[],[]]

  # empty result object
  result_obj = {
    'place_id': qobj['place_id'], 
    'title': qobj['title'], 
    'hits':[], 'missed':-1, 'total_hits':0,
    'hit_count': 0
  }  
  # de-dupe
  variants = list(set(qobj["variants"]))
  links = list(set(qobj["links"]))
  # copy for appends
  linklist = deepcopy(links)
  has_fclasses = len(qobj["fclasses"]) > 0

  # prep spatial constraints
  has_bounds = bounds["id"] != ["0"]
  has_geom = "geom" in qobj.keys()
  has_countries = len(qobj["countries"]) > 0
    
  if has_bounds:
    area_filter = get_bounds_filter(bounds, "whg")
    #print("area_filter", area_filter)
  if has_geom:
    # qobj["geom"] is always a polygon hull
    shape_filter = { "geo_shape": {
      "geoms.location": {
        "shape": {
          "type": qobj["geom"]["type"],
          "coordinates" : qobj["geom"]["coordinates"]},
        "relation": "intersects" }
    }}
    #print("shape_filter", shape_filter)
  if has_countries:
    countries_match = {"terms": {"ccodes":qobj["countries"]}}
    #print("countries_match", countries_match)
  
  """
  prepare queries from qobj
  """
  # q0 is matching concordance identifiers
  q0 = {
    "query": {"bool": { "must": [
      {"terms": {"links.identifier": linklist }}
    ]
  }}}


  # build q1 from qbase + spatial context, fclasses if any
  qbase = {"size": 100,"query": { 
    "bool": {
      "must": [
        {"exists": {"field": "whg_id"}},
        # must match one of these (exact)
        {"bool": {
            "should": [
              {"terms": {"names.toponym": variants}},
              {"terms": {"title": variants}},
              {"terms": {"searchy": variants}}
            ]
          }
        }
      ],
      "should": [
        # bool::"should" outside of "must" boosts score
        # {"terms": {"links.identifier": qobj["links"] }},
        {"terms": {"types.identifier": qobj["placetypes"]}}
      ],
      # spatial filters added according to what"s available
      "filter": []
    }
  }}

  # ADD SPATIAL
  if has_geom:
    qbase["query"]["bool"]["filter"].append(shape_filter)
    
  # no geom, use country codes if there
  if not has_geom and has_countries:
    qbase["query"]["bool"]["must"].append(countries_match)
    
  # has no geom but has bounds (region or user study area)
  if not has_geom and has_bounds:
    # area_filter (predefined region or study area)
    qbase["query"]["bool"]["filter"].append(area_filter)
    if has_countries:
      # add weight for country match
      qbase["query"]["bool"]["should"].append(countries_match)

  # ADD fclasses IF ANY
  # if has_fclasses:
  #   qbase["query"]["bool"]["must"].append(
  #   {"terms": {"fclasses": qobj["fclasses"]}})

  # grab a copy
  q1 = qbase
  print('q1', q1)

  # /\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
  # pass0a, pass0b (identifiers)
  # /\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
  try:
    result0a = es.search(index=idx, body=q0)
    hits0a = result0a["hits"]["hits"]
    #print('len(hits0)',len(hits0a))
  except:
    print("q0a, ES error:", q0, sys.exc_info())
  if len(hits0a) > 0:
    # >=1 matching identifier
    result_obj['hit_count'] += len(hits0a)
    for h in hits0a:
      # add full hit to result
      result_obj["hits"].append(h)
      # pull some fields for analysis
      h["pass"] = "pass0a"
      relation = h["_source"]["relation"]
      hitobj = {
        "_id":h['_id'],
        "pid":h["_source"]['place_id'], 
        "title":h["_source"]['title'],
        "dataset":h["_source"]['dataset'],
        "pass":"pass0",
        "links":[l["identifier"] \
            for l in h["_source"]["links"]],
        "role":relation["name"],
        "children":h["_source"]["children"]
      }        
      if "parent" in relation.keys():
        hitobj["parent"] = relation["parent"]
      # add profile to hitlist
      hitobjlist.append(hitobj)
    print(str(len(hitobjlist))+" hits @ q0a")
    _ids = [h['_id'] for h in hitobjlist]
    for hobj in hitobjlist:
      for l in hobj['links']:
        linklist.append(l) if l not in linklist else linklist

    # if new links, crawl again
    if len(set(linklist)-set(links)) > 0:
      try:
        print('q0 at 0b search, new link identifiers?', q0)
        result0b = es.search(index=idx, body=q0)
        hits0b = result0b["hits"]["hits"]
        print('len(hits0b)',len(hits0b))
      except:
        print("q0b, ES error:", sys.exc_info())
      # add new results if any to hitobjlist and result_obj["hits"]
      result_obj['hit_count'] += len(hits0b)
      for h in hits0b:
        if h['_id'] not in _ids:
          _ids.append(h['_id'])
          relation = h["_source"]["relation"]
          h["pass"] = "pass0b"        
          hitobj = {
            "_id":h['_id'],
            "pid":h["_source"]['place_id'],
            "title":h["_source"]['title'],
            "dataset":h["_source"]['dataset'],
            "pass":"pass0b",
            "links":[l["identifier"] \
                for l in h["_source"]["links"]],
            "role":relation["name"],
            "children":h["_source"]["children"]
          }        
          if "parent" in relation.keys():
            hitobj["parent"] = relation["parent"]
          if hitobj['_id'] not in [h['_id'] for h in hitobjlist]:
            result_obj["hits"].append(h)
            hitobjlist.append(hitobj)
          result_obj['total_hits'] = len((result_obj["hits"]))
      
  #   
  # /\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
  # run pass1 whether pass0 had hits or not
  # q0 only found identifier matches
  # now get other potential hits in normal manner
  # /\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
  try:
    result1 = es.search(index=idx, body=q1)
    hits1 = result1["hits"]["hits"]
  except:
    print("q1, ES error:", q1, sys.exc_info())  
    h["pass"] = "pass1"

  result_obj['hit_count'] += len(hits1)

  for h in hits1:
    # filter out _ids found in pass0
    # any hit on identifiers will also turn up here based on context
    if h['_id'] not in _ids:
      _ids.append(h['_id'])
      relation = h["_source"]["relation"]
      h["pass"] = "pass1"        
      hitobj = {
        "_id":h['_id'],
        "pid":h["_source"]['place_id'],
        "title":h["_source"]['title'],
        "dataset":h["_source"]['dataset'],
        "pass":"pass1",
        "links":[l["identifier"] \
            for l in h["_source"]["links"]],
        "role":relation["name"],
        "children":h["_source"]["children"]
      }        
      if "parent" in relation.keys():
        hitobj["parent"] = relation["parent"]
      if hitobj['_id'] not in [h['_id'] for h in hitobjlist]:
        # result_obj["hits"].append(hitobj)
        result_obj["hits"].append(h)
        hitobjlist.append(hitobj)
      result_obj['total_hits'] = len(result_obj["hits"])
  #ds_hits[p.id] = hitobjlist
  # no more need for hitobjlist
  
  # return index docs to align_idx() for Hit writing
  return result_obj

"""
# align/accession to whg index
# gets result_obj per Place
# writes 'union' Hit records to db for review
# OR writes seed parent to whg index 
"""
# TODO (1): "passive analysis option" reports unmatched and matched only
# TODO (2): "passive analysis option" that reports matches within datasets in a collection
# TODO (3): option with collection constraint; writes place_link records for partner records
@shared_task(name="align_idx")
def align_idx(*args, **kwargs):
  task_id = align_idx.request.id
  task_status = AsyncResult(task_id).status
  ds = get_object_or_404(Dataset, id=kwargs['ds'])
  print('kwargs in align_idx()',kwargs)
  test=kwargs['test']  # always 'on' for dev - no writing to the production index!

  idx = settings.ES_WHG
  print('idx in align_idx', idx)
  user = get_object_or_404(User, id=kwargs['user'])
  # get last index identifier (used for _id)
  whg_id = maxID(es, idx)

  # TODO: ?? open file for writing new seed/parents for inspection
  wd = "_scratch/"
  fn1 = "new-parents_"+str(ds.id)+".txt"
  fout1 = codecs.open(fn1, mode="w", encoding="utf8")
  
  # bounds = {'type': ['userarea'], 'id': ['0']}
  bounds = kwargs['bounds']
  scope = kwargs['scope']
  
  hit_parade = {"summary": {}, "hits": []}
  [count_hit,count_nohit,total_hits,count_p0,count_p1] = [0,0,0,0,0]
  [count_errors,count_seeds,count_kids,count_fail] = [0,0,0,0]
  new_seeds = [] # ids of places indexed immediately
  for_review = [] # ids of places for which there were hits
  start = datetime.datetime.now()
    
  # limit scope if some are already indexed
  qs = ds.places.filter(indexed=False)
  # TODO: scope = 'all' should be not possible for align_idx
  # qs = ds.places.all() if scope == 'all' else ds.places.filter(indexed=False) \
  #   if scope == 'unindexed' else ds.places.filter(review_wd != 1)
  
  """
  for each place, create qobj and run es_lookup_idx(qobj)
  if hits: write Hit instances for review
  if no hits: write new parent doc in index
  """
  for p in qs:
    qobj = build_qobj(p)
    
    result_obj = es_lookup_idx(qobj, bounds=bounds)
    
    # PARSE RESULTS
    # no hits on any pass, index as new seed/parent
    if len(result_obj['hits']) == 0:
      # create new parent
      whg_id +=1
      doc = makeDoc(p)
      doc['relation']['name'] = 'parent'
      doc['whg_id'] = whg_id
      # get names for search fields
      names = [p.toponym for p in p.names.all()]
      doc['searchy'] = names
      print("seed", whg_id, doc)
      new_seeds.append(p.id)
      if test == 'off':
        res = es.index(index=idx, id=str(whg_id), document=json.dumps(doc))
        p.indexed = True
        p.save()

    # got some hits, format json & write to db as for align_wdlocal, etc.
    elif len(result_obj['hits']) > 0:
      count_hit +=1  # this record got >=1 hits
      # set place/task status to 0 (has unreviewed hits)
      p.review_whg = 0
      p.save()
      for_review.append(p.id)

      hits = result_obj['hits']
      [count_kids,count_errors] = [0,0]
      total_hits += result_obj['total_hits']

      # identify parents and children
      parents = [profileHit(h) for h in hits \
                if h['_source']['relation']['name']=='parent']
      children = [profileHit(h) for h in hits \
                if h['_source']['relation']['name']=='child']

      """ *** """
      p0 = len(set(['pass0a','pass0b']) & set([p['pass'] for p in parents])) > 0
      p1 = 'pass1' in [p['pass'] for p in parents]
      if p0:
        count_p0 += 1
      elif p1:
        count_p1 +=1

      def uniq_geom(lst):
        for _, grp in itertools.groupby(lst, lambda d: (d['coordinates'])):
          yield list(grp)[0]

      # if there are any
      for par in parents:
        # 20220828 test
        print('parent minmax', par['minmax'])
        # any children of *this* parent in this result?
        kids = [c for c in children if c['_id'] in par['children']] or None
        # merge values into hit.json object
        # profile keys ['_id', 'pid', 'title', 'role', 'dataset', 'parent', 'children', 'links', 'countries', 'variants', 'geoms']
        # boost parent score if kids
        score = par['score']+sum([k['score'] for k in kids]) if kids else par['score']
        #
        hitobj = {
          'whg_id': par['_id'],
          'pid': par['pid'],
          'score': score,
          'titles': [par['title']],
          'countries': par['countries'],
          'geoms': list(uniq_geom(par['geoms'])),
          'links': par['links'],
          'sources': [
            {'dslabel': par['dataset'], 
             'pid': par['pid'],
             'variants': par['variants'],
             'types': par['types'],
             'related': par['related'],
             'children': par['children'],
             'minmax': par['minmax'],
             'pass': par['pass'][:5]
             }]
        }
        if kids:
          hitobj['titles'].extend([k['title'] for k in kids])
          hitobj['countries'].extend([','.join(k['countries']) for k in kids])
          
          # unnest
          if hitobj['geoms']:
            hitobj['geoms'].extend(list(chain.from_iterable([k['geoms'] for k in kids])))
          if hitobj['links']:
            hitobj['links'].extend(list(chain.from_iterable([k['links'] for k in kids])))
          
          # add kids to parent in sources
          hitobj['sources'].extend(
            [{'dslabel':k['dataset'],
              'pid':k['pid'],
              'variants':k['variants'],
              'types':k['types'],
              'related': par['related'],
              'minmax':k['minmax'],
              'pass':k['pass'][:5]} for k in kids])

        passes = list(set([s['pass'] for s in hitobj['sources']]))
        hitobj['passes'] = passes

        hitobj['titles'] = ', '.join(list(dict.fromkeys(hitobj['titles'])))
        
        if hitobj['links']:
          hitobj['links'] = list(dict.fromkeys(hitobj['links']))
  
        hitobj['countries'] = ', '.join(list(dict.fromkeys(hitobj['countries'])))

        new = Hit(
          task_id = task_id,
          authority = 'whg',
          
          # incoming place
          dataset = ds,
          place = p, 
          src_id = p.src_id,
          
          # candidate parent, might have children
          authrecord_id = par['_id'],
          query_pass = ', '.join(passes), #
          score = hitobj['score'],
          geom = hitobj['geoms'],
          reviewed = False,
          matched = False,
          json = hitobj
        )
        new.save()
        #print(json.dumps(jsonic,indent=2))
  
  # testing: write new index seed/parent docs for inspection
  # fout1.write(str(new_seeds))
  # fout1.write('\n\nFor Review\n'+str(for_review))
  # fout1.close()
  # print(str(len(new_seeds)+len(for_review)) + ' IDs written to '+ fn1)
  
  end = datetime.datetime.now()
  
  hit_parade['summary'] = {
    'count':qs.count(), # records in dataset
    'got_hits':count_hit, # count of parents
    'total_hits': total_hits, # overall total
    'seeds': len(new_seeds), # new index seeds
    'pass0': count_p0, 
    'pass1': count_p1, 
    'elapsed_min': elapsed(end-start),
    'skipped': count_fail
  }
  print("hit_parade['summary']",hit_parade['summary'])
  
  # create log entry and update ds status
  post_recon_update(ds, user, 'idx', test)

  # email owner when complete
  # tid, dslabel, name, email, counthit, totalhits, test
  from utils.emailing import new_emailer
  new_emailer(
    email_type='align_idx',
    subject='WHG alignment task complete',
    from_email=settings.DEFAULT_FROM_EMAIL,
    to_email=[user.email],
    name=user.username,
    greeting_name=user.name if user.name else user.username,
    dslabel=ds.label,
    dstitle=ds.title,
    email=user.email,
    # TODO: get correct counts for message
    counthit=count_hit,  # of records with any hit(s)
    totalhits=total_hits,  # of hits
    taskname='WHG index',
    status=task_status,
    test=test
  )

  print('elapsed time:', elapsed(end-start))


  return hit_parade['summary']

