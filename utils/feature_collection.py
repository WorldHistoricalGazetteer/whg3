# feature_collection.py

from django.contrib.gis.geos import GEOSGeometry
from geojson import Feature
from places.models import PlaceGeom
import numpy as np
import simplejson as json

def feature_collection(caller):
    
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__   
    
    feature_collection = {
        "type": "FeatureCollection",
        "features": [],
    }
    geom_list = None
    
    if caller_class == 'Dataset':
        geom_list = PlaceGeom.objects.filter(place_id__in=caller.placeids).values_list('jsonb', flat=True)
    else: # caller_class == 'Collection'
        places = caller.places_all
        if places.count() > 0:
            geom_list = [geom.jsonb for place in places for geom in place.geoms.all()]
            
    if geom_list:
        for geometry in geom_list:
            feature_collection['features'].append(Feature(geometry=geometry, properties={'mode': 'feature_collection'}))

    return feature_collection
