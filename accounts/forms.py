import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

User = get_user_model()
# from accounts.models import Profile

URL_PATTERN = re.compile(r'https?://|www\.|tinyurl\.com|bit\.ly|\/')


def validate_no_urls(value):
    if URL_PATTERN.search(value):
        if value and URL_PATTERN.search(value):
            raise ValidationError('Please do not include URLs or links in this field.')


class LoginForm(forms.Form):
    username = forms.CharField(max_length=100, required=True)
    email = forms.CharField(max_length=255, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def clean(self):
        name = self.cleaned_data.get('name')
        username = self.cleaned_data.get('username')
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        user = authenticate(email=email, password=password)
        if not user or not user.is_active:
            raise forms.ValidationError("Sorry, that login was invalid. Please try again.")
        return self.cleaned_data

    def login(self, request):
        username = self.cleaned_data.get('username')
        name = self.cleaned_data.get('name')
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        user = authenticate(username=username, password=password)
        # user = authenticate(email=email, password=password)
        return user


class UserModelForm(forms.ModelForm):
    class Meta:
        model = User
        # fields = ('username', 'email', 'given_name', 'surname', 'name', 'affiliation',
        #           'role', 'web_page', 'image_file')
        # fields = ('username', 'email', 'given_name', 'surname', 'affiliation',
        #           'role', 'web_page', 'image_file')
        fields = ('news_permitted',)
        exclude = ('password',)

        widgets = {
            # 'username': forms.TextInput(attrs={'size': 50}),
            # 'email': forms.TextInput(attrs={'size': 50}),
            # # 'name': forms.TextInput(attrs={'size': 50}),
            # 'given_name': forms.TextInput(attrs={'size': 50}),
            # 'surname': forms.TextInput(attrs={'size': 50}),
            # 'affiliation': forms.TextInput(attrs={'size': 50}),
            # 'web_page': forms.TextInput(attrs={'size': 50}),
            # 'image_file': forms.FileInput(attrs={'class': 'fileinput'}),
            'news_permitted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # def clean_username(self):
    #     username = self.cleaned_data.get('username', '')
    #     # Check for obvious URL patterns in usernames
    #     validate_no_urls(username)
    #     return username
    #
    # def clean_given_name(self):
    #     given_name = self.cleaned_data.get('given_name', '')
    #     validate_no_urls(given_name)
    #     return given_name
    #
    # def clean_surname(self):
    #     surname = self.cleaned_data.get('surname', '')
    #     validate_no_urls(surname)
    #     return surname
    #
    # def clean_email(self):
    #     email = self.cleaned_data.get('email')
    #     try:
    #         validate_email(email)
    #     except ValidationError:
    #         raise ValidationError("Invalid email address")
    #     return email
    #
    # def clean(self):
    #     cleaned_data = super().clean()
    #     for field in self.Meta.fields:
    #         if field not in cleaned_data and self.fields[field].required and not self.errors.get(field):
    #             self.add_error(field, "This field is required")
    #     return cleaned_data
    #
    # def __init__(self, *args, **kwargs):
    #     super(UserModelForm, self).__init__(*args, **kwargs)
    #     self.fields['affiliation'].required = False
    #     self.fields['role'].required = False
    #     self.fields['image_file'].required = False
