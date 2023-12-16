# carousel_metadata.py

from django.urls import reverse

def carousel_metadata(caller):
    
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__
    
    display_mode = getattr(caller, 'display_mode', None) or '' # 'clusterhull'|'heatmap'|'convexhull'|'feature_collection'(default) implemented
    
    if caller_class == 'Dataset':
        url = reverse('datasets:ds_places', args=[caller.id])
        id_name = 'id'
        pass
    elif caller_class == 'Collection':
        url = reverse('collection:ds-collection-browse', args=[caller.id])
        id_name = 'coll'
        pass
    else:
        # Handle other cases or raise an exception
        raise ValueError("Unsupported caller class: {}".format(caller_class))

    return {
        "title": caller.title,
        "image_file": caller.image_file.url if caller.image_file else None,
        "description": caller.description,
        "creator": caller.creator,
        "owner": caller.owner.name,
        "type": caller_class.lower(), 
        "featured": caller.featured,
        "ds_or_c_id": caller.id, 
        "display_mode": display_mode,
        "webpage": caller.webpage,
        "url": url,
        "geometry_url": f"/api/featureCollection/?{id_name}={caller.id}&mode={display_mode}",
    }
