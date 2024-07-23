# traces.forms
from django import forms
from django.db import models
from django.core.exceptions import ValidationError
from .models import TraceAnnotation
import re

def valid_dates(value):
    # Regular expression to match dates in formats: YYYY, YYYY-MM, YYYY-MM-DD
    # Allows years up to 6 digits, optional negative sign for BCE years
    if not re.match(r'^-?\d{1,6}(-\d{2})?(-\d{2})?$', value):
        raise ValidationError(
            f'Enter a valid date in one of the formats: YYYY, YYYY-MM, YYYY-MM-DD, with optional negative year ({value} is invalid).'
        )

class TraceAnnotationModelForm(forms.ModelForm):
	start = forms.CharField(validators=[valid_dates], widget=forms.TextInput(attrs={'size': 11, 'placeholder': 'yyyy-mm-dd'}))
	end = forms.CharField(validators=[valid_dates], widget=forms.TextInput(attrs={'size': 11, 'placeholder': 'yyyy-mm-dd'}))
	
	class Meta:
		model = TraceAnnotation
		fields = ('id', 'note', 'relation', 'start', 'end', 'sequence', 'anno_type', 'motivation',
		          'owner', 'collection', 'place', 'image_file','saved')
		widgets = {
			# 'collection': forms.TextInput(attrs={'size': 4}),
			'note': forms.Textarea(attrs={'rows':4,'cols': 38,'class':'textarea'}),
			'collection': forms.TextInput(attrs={'size': 4}),
			'place': forms.TextInput(attrs={'size': 16}),
			'relation': forms.Select(),
			'start': forms.TextInput(attrs={'size': 11, 'placeholder':'yyyy-mm-dd'}),
			'end': forms.TextInput(attrs={'size': 11, 'placeholder':'yyyy-mm-dd'}),
			# 'image_file': forms.ImageField()
			'image_file': forms.FileInput()
		}

	def __init__(self, *args, **kwargs):
		super(TraceAnnotationModelForm, self).__init__(*args, **kwargs)
