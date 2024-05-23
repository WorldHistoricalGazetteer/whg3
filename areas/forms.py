from django import forms
from django.contrib.gis.geos import GEOSGeometry, GeometryCollection
from django.core.exceptions import ValidationError
from django.db import models
# from leaflet.forms.widgets import LeafletWidget
from .models import Area
import json

class AreaModelForm(forms.ModelForm):
    # ** trying to return to referrer
    next = forms.CharField(required=False)
    # **
    
    class Meta:
        model = Area
        #exclude = tuple()
        fields = ('id','type','owner','title','description','ccodes','geojson','next')
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Enter a title'
            }),
            'description': forms.Textarea(attrs={
                'rows':2,'cols': 40,'class':'textarea',
                'placeholder':'Enter a description for this Study Area'
            }),
            'ccodes': forms.TextInput(attrs={
                'placeholder':'2-letter codes, e.g. BR,AR',
                'size': 30
            }),
            'geojson': forms.Textarea(attrs={
                'id': 'geojson',
                'rows':2,'cols': 40,'class':'textarea',
                'placeholder':'(filled automatically)',
                'disabled': 'True',
            }),
        }


    def __init__(self, *args, **kwargs):
        super(AreaModelForm, self).__init__(*args, **kwargs)
        if 'geojson' not in self.initial:
            self.initial['geojson'] = None

    def clean_geojson(self):
        geojson_data = self.cleaned_data['geojson']

        try:
            geometry = GEOSGeometry(json.dumps(geojson_data))
            geometry = geometry.simplify(0.00001).buffer(0) # Simplify and clean
            collection = GeometryCollection(geometry)
            return json.loads(collection.geojson)
            
        except Exception as e:
            raise ValidationError(f"Invalid GeoJSON: {e}")

        return None

#class AreaDetailModelForm(forms.ModelForm):
    #class Meta:
        #model = Area
        #fields = ('id','type','owner','title','description','ccodes','geojson')
        #widgets = {
            #'description': forms.Textarea(attrs={
                #'rows':1,'cols': 60,'class':'textarea','placeholder':'brief description'}),
        #}

    #def __init__(self, *args, **kwargs):
        #super(AreaDetailModelForm, self).__init__(*args, **kwargs)
