# carousel_metadata.py

from django.urls import reverse
import traceback

def carousel_metadata(caller):
    # traceback.print_stack()
    # Detect the class of the caller
    caller_class = type(caller)
    caller_class = caller_class.__name__
    
    display_mode = getattr(caller, 'display_mode', None) or '' # 'clusterhull'|'heatmap'|'convexhull'|'feature_collection'(default) implemented
    
    #############################################################################
    #############################################################################
    # TODO: THIS CODE BLOCK SHOULD BE REMOVED ONCE VALUES ARE PRESENT IN DATABASE
    default_display_modes = {
        ('Dataset', 9): 'heatmap',
        ('Dataset', 10): 'heatmap',
        ('Dataset', 12): 'heatmap',
        ('Dataset', 13): 'convexhull', # US Counties - prime candidate for database storage - clusterhull would require >7TiB of memory for on-the-fly generation
        ('Dataset', 29): 'heatmap',
        ('Dataset', 38): 'clusterhull',
        ('Dataset', 40): 'heatmap',
        ('Collection', 2): 'heatmap',
        ('Collection', 11): 'clusterhull',
        ('Collection', 12): 'clusterhull',
        ('Collection', 13): 'convexhull',
    }
    if not display_mode or len(display_mode.strip()) == 0:
        default_key = (caller_class, caller.id)
        display_mode = default_display_modes.get(default_key, '')
        # print("Please remember to remove default display mode casting in `utils/carousel_metadata.py`.")
    #############################################################################
    #############################################################################
    
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
