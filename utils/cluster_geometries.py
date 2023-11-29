# cluster_geometries.py

from django.urls import reverse
from django.contrib.gis.geos import GEOSGeometry, Point, MultiPoint
from places.models import PlaceGeom
import numpy as np
import simplejson as json
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import calinski_harabasz_score

def clustered_geometries(caller, bare=False):
    
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__
    
    if caller_class == 'Dataset':
        url = reverse('datasets:ds_places', args=[caller.id])
        pass
    elif caller_class == 'Collection':
        url = reverse('collection:ds-collection-browse', args=[caller.id])
        pass
    else:
        # Handle other cases or raise an exception
        raise ValueError("Unsupported caller class: {}".format(caller_class))    
    
    # Initialize the clustered features with common properties
    clustered_geometries = {
        "properties": {},
        "type": "Feature",
        "geometry": {"type": "GeometryCollection", "geometries": []}
    }
    
    if not bare:
        clustered_geometries['properties'] = {
            "title": caller.title,
            "image_file": caller.image_file.url if caller.image_file else None,
            "description": caller.description,
            "creator": caller.creator,
            "type": caller_class.lower(), 
            "featured": caller.featured,
            "ds_or_c_id": caller.id, 
            "webpage": caller.webpage,
            "url": url,
        }

    def flatten_coordinates(coord): # Required to cope with nested GeometryCollections and MultiGeometries
        flattened = []
        for element in coord:
            if isinstance(element, tuple):
                flattened.extend(flatten_coordinates(element))
            else:
                flattened.append(element)
        return flattened
    
    coordinates = []
    
    if caller_class == 'Dataset':
        dsgeoms = PlaceGeom.objects.filter(place__dataset=caller)
        if not dsgeoms:
            return clustered_geometries
        for geom in dsgeoms:
            coords = GEOSGeometry(geom.geom).tuple
            coordinates.extend( flatten_coordinates(coords) )
    else: # caller_class == 'Collection'
        places = caller.places.all()
        if not places:
            return clustered_geometries
        for place in places:
            for geom in place.geoms.all():
                coords = GEOSGeometry(geom.geom).tuple
                coordinates.extend( flatten_coordinates(coords) )
            
    # Reshape the flat list into coordinate tuples
    coordinates = np.array([coordinates[i:i+2] for i in range(0, len(coordinates), 2)])
    
    # Perform Agglomerative Clustering
    max_clusters = 10
    calinski_scores = []
    
    for n_clusters in range(2, max_clusters + 1):
        clusterer = AgglomerativeClustering(n_clusters=n_clusters)
        labels = clusterer.fit_predict(coordinates)
        calinski_score = calinski_harabasz_score(coordinates, labels)
        calinski_scores.append(calinski_score)
    
    # Find the "elbow" point using the first derivative
    deltas = np.diff(calinski_scores)
    elbow_index = np.argmax(deltas < np.mean(deltas) / 2) + 1
    optimal_clusters = elbow_index + 1  # Add 1 because of 0-based indexing
    
    # Perform clustering with the optimal number of clusters
    clusterer = AgglomerativeClustering(n_clusters=optimal_clusters)
    labels = clusterer.fit_predict(coordinates)
    
    # Keep track of which labels have been processed
    processed_labels = set()
    
    # Create features using convex hull for clusters with more than 2 members
    for i, coord in enumerate(coordinates):
        current_label = labels[i]
        
        # Check if the label has been processed
        if current_label not in processed_labels:
            members_indices = np.where(labels == current_label)[0]
    
            # Check if there are more than 2 members in the cluster
            if len(members_indices) > 2:
                # Create convex hull polygon using Django's convex_hull method
                cluster_points = [GEOSGeometry(f"POINT ({coord[0]} {coord[1]})") for coord in coordinates[members_indices]]
                multipoint_geom = MultiPoint(cluster_points)
                convex_hull = multipoint_geom.convex_hull
                geometry = json.loads(GEOSGeometry(convex_hull).geojson)
                clustered_geometries['geometry']['geometries'].append(geometry)
            else:
                # Create points for clusters with 1 or 2 members
                for member_index in members_indices:
                    geometry = {
                        "type": "Point",
                        "coordinates": coordinates[member_index].tolist(),
                    }
                    clustered_geometries['geometry']['geometries'].append(geometry)
    
            processed_labels.add(current_label)

    return clustered_geometries
