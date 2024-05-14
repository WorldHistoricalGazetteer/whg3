# carousel_metadata.py

from django.urls import reverse
import traceback

def carousel_metadata(caller):
    # traceback.print_stack()
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__
    
    display_mode = getattr(caller, 'display_mode') or ''
    
    if caller_class == 'Dataset':
        url = reverse('datasets:ds_places', args=[caller.id])
        id_name = 'id'
        pass
    elif caller_class == 'Collection':
        if caller.collection_class == 'dataset':
            url = reverse('collection:ds-collection-browse', args=[caller.id])
        elif caller.collection_class == 'place':
            url = reverse('collection:place-collection-browse', args=[caller.id])
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
        "contributors": caller.contributors if caller_class == 'Dataset' else '',
        "owner": caller.owner.name,
        "type": caller_class.lower(), 
        "featured": caller.featured,
        "ds_or_c_id": caller.id, 
        "display_mode": display_mode,
        "webpage": caller.webpage,
        "url": url,
        "geometry_url": f"/api/featureCollection/?{id_name}={caller.id}&mode={display_mode}",
    }