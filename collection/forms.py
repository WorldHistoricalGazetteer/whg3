from django import forms
from django.db import models
from django.template.loader import render_to_string
from django.utils.functional import lazy

from .models import Collection, CollectionGroup, CollectionLink

render_tooltip = lazy(lambda: render_to_string('includes/tooltip_contributors.html'), str)

class CollectionGroupModelForm(forms.ModelForm):
    # create and/or edit CollectionGroup
    class Meta:
        model = CollectionGroup
        fields = ('id', 'title', 'owner', 'description', 'keywords',
                  'start_date', 'due_date', 'gallery', 'gallery_required',
                  'collaboration', 'type', 'file',)
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2, 'cols': 40, 'class': 'textarea'
            }),
            'title': forms.TextInput(attrs={
                'size': 30
            }),
            'keywords': forms.TextInput(attrs={
                'placeholder': 'e.g. journey, Central Asia',
                'size': 30
            }),
            'type': forms.Select,
            'start_date': forms.SelectDateWidget,
            'due_date': forms.SelectDateWidget,
            'file': forms.FileInput(),
            'gallery': forms.CheckboxInput,
            'gallery_required': forms.CheckboxInput,
            'collaboration': forms.CheckboxInput
        }

    def __init__(self, *args, **kwargs):
        super(CollectionGroupModelForm, self).__init__(*args, **kwargs)


class CollectionLinkForm(forms.ModelForm):
    class Meta:
        model = CollectionLink
        fields = ('collection', 'uri', 'label', 'link_type')
        widgets = {
            'uri': forms.URLInput,
            'label': forms.TextInput(attrs={'size': 50}),
            'link_type': forms.Select()
        }

    def __init__(self, *args, **kwargs):
        super(CollectionLinkForm, self).__init__(*args, **kwargs)

class CollectionModelForm(forms.ModelForm):

    # ** trying to return to referrer
    next = forms.CharField(required=False)

    class Meta:
        model = Collection
        fields = ('id', 'owner', 'title','collection_class', 'description', 'keywords', 'rel_keywords',
                  'image_file', 'file', 'datasets', 'creator', 'contact', 'webpage', 'featured',
                  'status', 'group', 'vis_parameters', 'public')

        widgets = {
            # 'title': forms.TextInput(attrs={'size': 45}),
            'title': forms.TextInput(attrs={'size': 45}),
            'keywords': forms.TextInput(attrs={'placeholder': 'comma-delimited', 'size': 45}),
            'rel_keywords': forms.TextInput(attrs={'size': 45, 'placeholder':'comma-delimited'}),
            'creator': forms.TextInput(attrs={
                'size': 45,
                'data-bs-toggle': 'tooltip',
                'data-bs-title': render_tooltip(),
            }),
            'contact': forms.TextInput(attrs={'size': 45}),
            'webpage': forms.TextInput(attrs={'size': 45}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'textarea',
                'placeholder': 'A single paragraph. Note that a PDF file of any length can be uploaded later as well.'}),
            'image_file': forms.FileInput(attrs={'class': 'fileinput'}),
            'file': forms.FileInput(attrs={'class': 'fileinput'}),
            'datasets': forms.CheckboxSelectMultiple,
            'featured': forms.TextInput(attrs={'size': 3}),
            'group': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(CollectionModelForm, self).__init__(*args, **kwargs)
        user_groups = CollectionGroup.objects.filter(members__user=self.user)
        self.fields['group'].queryset = user_groups
        if self.instance.status == 'nominated':
            self.fields['group'].disabled = True