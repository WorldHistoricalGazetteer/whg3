# /utils/country_feature_collection.py
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q
from areas.models import Area
import json

def get_country_feature_collection():
    regions = Area.objects.all().filter((Q(type='predefined'))).values('id','type','title','geojson')
    countries = Area.objects.all().filter((Q(type='country'))).values('id','type','title','ccodes','geojson')
    country_codes = {country['id']: country['ccodes'] for country in countries}
    country_geometries = {country['id']: GEOSGeometry(json.dumps(country['geojson'])) for country in countries}
    
    # TODO: This code block would be unnecessary if all predefined areas had populated ccodes in database
    for region in regions:
        region_geojson = GEOSGeometry(json.dumps(region['geojson']))
        intersecting_ccodes = []
    
        # Check intersection with each country
        for country_id, country_geometry in country_geometries.items():
            if region_geojson.intersects(country_geometry):
                intersecting_ccodes.extend(country_codes[country_id])
    
        region['ccodes'] = intersecting_ccodes
            
    # Transform lists for grouping in dropdown
    regions = [{'id': region['id'], 'text': region['title'], 'ccodes': region['ccodes']} for region in sorted(regions, key=lambda x: x['title'])]
    countries = [{'id': country['ccodes'][0], 'text': country['title']} for country in sorted(countries, key=lambda x: x['title'])]

    dropdown_data = [{'text':'Regions', 'children': list(regions)}, {'text': 'Countries', 'children': list(countries)}]
    
    return json.dumps(dropdown_data, default=str)
