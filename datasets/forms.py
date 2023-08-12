# datasets.forms

from django import forms
from django.core.exceptions import ValidationError
from datasets.models import Dataset, Hit, DatasetFile
from datasets.utils import insert_delim, insert_lpf, validator_delim, validate_lpf, sniff_file_type
from main.choices import FORMATS, STATUS_FILE

MATCHTYPES = [
    ('closeMatch', 'closeMatch'),
    ('none', 'no match'),
]

# ***
# will replace DatasetCreateModelForm()
# ***
class DatasetCreateForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ('owner', 'id', 'title', 'label', 'datatype', 'description', 'uri_base', 'public',
                  'creator', 'contributors', 'source', 'webpage', 'image_file', 'featured')
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2, 'cols': 45, 'class': 'textarea', 'placeholder': 'Brief description'}),
            'uri_base': forms.URLInput(attrs={
                    'placeholder': 'Leave blank unless record IDs are URIs', 'size': 45}),
            'title': forms.TextInput(attrs={'size': 45}),
            'label': forms.TextInput(attrs={'placeholder': '20 char max; no spaces','size': 22}),
            'creator': forms.TextInput(attrs={'size': 45}),
            'source': forms.TextInput(attrs={'size': 45}),
            'featured': forms.TextInput(attrs={'size': 4}),
            'webpage': forms.URLInput(attrs={'size': 45, 'placeholder': 'Project home page, if any'})
        }

    def clean(self):
        cleaned_data = super().clean()

        file = cleaned_data.get('file')

        if file:
            file_type = sniff_file_type(file)  # implement this function

            if file_type == 'delimited':
                validation_result = validator_delim(file)
            elif file_type == 'json':
                validation_result = validator_lpf(file)
            else:
                raise ValidationError('Invalid file type')

            if validation_result != 'Validation passed':
                raise ValidationError(validation_result)

        return cleaned_data

    def clean_label(self):
        label = self.cleaned_data['label']
        if ' ' in label:
            raise forms.ValidationError('Label cannot contain any spaces; replace with underscores (_)')
        return label

    def save(self, commit=True):
        instance = super().save(commit=commit)  # Save Dataset instance

        file = self.cleaned_data.get('file')

        if file:
            file_type = sniff_file_type(file)  # implement this function

            try:
                if file_type == 'delimited':
                    insert_delim(file, instance.label)
                elif file_type == 'json':
                    insert_lpf(file, instance.label)
            except Exception as e:
                # Catch any exceptions that occur during database insertion and turn them into validation errors
                raise ValidationError(f'An error occurred while inserting data into the database: {str(e)}')

        return instance

class DatasetCreateModelForm(forms.ModelForm):
    class Meta:
        model = Dataset
        # file fields = ('file','rev','uri_base','format','dataset_id','delimiter',
        #   'status','accepted_date','header','numrows')
        fields = ('owner', 'id', 'title', 'label', 'datatype', 'description', 'uri_base', 'public',
                  'creator', 'contributors', 'source', 'webpage', 'image_file', 'featured')
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2, 'cols': 45, 'class': 'textarea', 'placeholder': 'Brief description'}), 
            'uri_base': forms.URLInput(attrs={
                    'placeholder': 'Leave blank unless record IDs are URIs', 'size': 45}), 
            'title': forms.TextInput(attrs={'size': 45}),
            'label': forms.TextInput(attrs={'placeholder': '20 char max; no spaces','size': 22}),
            'creator': forms.TextInput(attrs={'size': 45}),
            'source': forms.TextInput(attrs={'size': 45}), 
            'featured': forms.TextInput(attrs={'size': 4}), 
            'webpage': forms.URLInput(attrs={'size': 45, 'placeholder': 'Project home page, if any'})
        }

    def clean_label(self):
        label = self.cleaned_data['label']
        if ' ' in label:
            raise forms.ValidationError('Label cannot contain any spaces; replace with underscores (_)')
        return label

    # fields used to create new DatasetFile record from form
    # uri_base = forms.URLField(widget=forms.URLInput(
        # attrs={'placeholder':'Leave blank unless record IDs are URIs','size':35}))
    file = forms.FileField()
    rev = forms.IntegerField()
    format = forms.ChoiceField(
        choices=FORMATS, widget=forms.RadioSelect, initial='delimited')
    delimiter = forms.CharField()
    header = forms.CharField()
    df_status = forms.ChoiceField(choices=STATUS_FILE)
    numrows = forms.IntegerField()
    upload_date = forms.DateTimeField()

    def __init__(self, *args, **kwargs):
        super(DatasetCreateModelForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'The field {fieldname} is required'.format(
                fieldname=field.label)}

class HitModelForm(forms.ModelForm):
    match = forms.CharField(
        initial='none',
        widget=forms.RadioSelect(choices=MATCHTYPES)
    )

    class Meta:
        model = Hit
        fields = ['id', 'authority', 'authrecord_id',
                  'query_pass', 'score', 'json']
        hidden_fields = ['id', 'authority',
                         'authrecord_id', 'query_pass', 'score', 'json']
        widgets = {
            'id': forms.HiddenInput(),
            'authority': forms.HiddenInput(),
            'authrecord_id': forms.HiddenInput(),
            'json': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        super(HitModelForm, self).__init__(*args, **kwargs)

        for key in self.fields:
            self.fields[key].required = False

class DatasetFileModelForm(forms.ModelForm):
    class Meta:
        model = DatasetFile
        fields = ('dataset_id', 'file', 'rev', 'format', 'delimiter',
                  'df_status', 'datatype', 'header', 'numrows')

    def __init__(self, *args, **kwargs):
        super(DatasetFileModelForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'The field {fieldname} is required'.format(
                fieldname=field.label)}

class DatasetDetailModelForm(forms.ModelForm):
    class Meta:
        model = Dataset
        # file fields = ('file','rev','uri_base','format','dataset_id','delimiter',
        #   'status','accepted_date','header','numrows')
        fields = ('owner', 'creator', 'contributors', 'source', 'id', 'label', 'title', 'uri_base', 'description',
                  'citation', 'datatype', 'numlinked', 'webpage', 'featured', 'image_file', 'public')
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2, 'cols': 55, 'class': 'textarea', 'placeholder': 'Brief description'}),
            'citation': forms.Textarea(attrs={
                'rows': 2, 'cols': 55, 'class': 'textarea'}),
            'creator': forms.TextInput(attrs={'size': 50}),
            'source': forms.TextInput(attrs={'size': 50}),
            'contributors': forms.TextInput(attrs={'size': 50}),
            'webpage': forms.TextInput(attrs={'size': 50}),
            # 'uri_base': forms.TextInput(attrs={'size': 50}),
            'uri_base': forms.URLInput(attrs={'size': 50}),
            'featured': forms.TextInput(attrs={'size': 4})
        }

    def clean_label(self):
        label = self.cleaned_data['label']
        if ' ' in label:
            print("there's a space goddamit")
            raise forms.ValidationError('label cannot contain any space')
        return label

    file = forms.FileField(required=False)
    uri_base = forms.URLField(
        widget=forms.URLInput(
            attrs={'placeholder': 'Leave blank unless changed', 'size': 40}
        ),
        required=False
    )
    format = forms.ChoiceField(choices=FORMATS, initial="delimited")

    def __init__(self, *args, **kwargs):
        super(DatasetDetailModelForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'The field {fieldname} is required'.format(
                fieldname=field.label)}

class DatasetCreateEmptyModelForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ('owner', 'id', 'title', 'label', 'datatype', 'description', 'uri_base', 'public',
                  'creator', 'contributors', 'source', 'webpage', 'image_file', 'featured', 'ds_status')

        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2, 'cols': 45, 'class': 'textarea', 'placeholder': 'Brief description'}),
            'uri_base': forms.URLInput(attrs={
                    'placeholder': 'Leave blank unless record IDs are URIs', 'size': 45}),
            'title': forms.TextInput(attrs={'size': 45}),
            'label': forms.TextInput(attrs={'placeholder': '20 char max; no spaces','size': 22}),
            'creator': forms.TextInput(attrs={'size': 45}),
            'source': forms.TextInput(attrs={'size': 45}),
            'featured': forms.TextInput(attrs={'size': 4}),
            'webpage': forms.URLInput(attrs={'size': 45, 'placeholder': 'Project home page, if any'})
        }

    def clean_label(self):
        label = self.cleaned_data['label']
        if ' ' in label:
            raise forms.ValidationError('Label cannot contain any spaces; replace with underscores (_)')
        return label

    def __init__(self, *args, **kwargs):
        super(DatasetCreateEmptyModelForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'The field {fieldname} is required'.format(
                fieldname=field.label)}

