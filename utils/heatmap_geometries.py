# heatmapped_geometries.py

from django.contrib.gis.geos import GEOSGeometry, Point
from geojson import Feature, Point
from places.models import PlaceGeom
import numpy as np
import simplejson as json

def heatmapped_geometries(caller):
    
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__   
    
    heatmapped_geometries = {
        "type": "FeatureCollection",
        "features": [],
    }
    
    def add_geometry(geometry):
        zero_dimension_factor = 5 # This will need to be adjusted

        area = None
        centroid = None
        
        print(geometry)

        # Calculate area and centroid based on geometry type
        if geometry.geom_type == 'Point':
            # For Point, use the point as centroid and calculate area for a circle with diameter zero_dimension_factor
            centroid = geometry
            area = 3.14159 * (zero_dimension_factor / 2) ** 2  # A = πr^2
        elif geometry.geom_type == 'LineString':
            # For LineString, use the centroid and calculate area as length times zero_dimension_factor
            centroid = geometry.centroid
            area = geometry.length * zero_dimension_factor
        elif geometry.geom_type in ['Polygon', 'MultiPolygon']:
            # For Polygon or MultiPolygon, use the provided area and centroid
            area = geometry.area
            centroid = geometry.centroid

        heatmapped_geometries['features'].append(Feature(
            geometry=Point(coordinates=(centroid.x, centroid.y) if centroid else None),
            properties={'area': area, 'mode': 'heatmap'}
        ))
    
    if caller_class == 'Dataset':
        dsgeoms = PlaceGeom.objects.filter(place__dataset=caller)
        if not dsgeoms:
            return heatmapped_geometries
        for dsgeom in dsgeoms:
            add_geometry(dsgeom.geom)

    else: # caller_class == 'Collection'
        places = caller.places.all()
        if not places:
            return heatmapped_geometries
        for place in places:
            for placegeom in place.geoms.all():
                add_geometry(placegeom.geom)

    return heatmapped_geometries
