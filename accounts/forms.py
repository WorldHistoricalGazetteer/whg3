from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

User = get_user_model()
# from accounts.models import Profile

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

# used to edit
class UserModelForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'name',
                  'role', 'web_page', 'image_file')
        exclude = ('password',)

        widgets = {
            'username': forms.TextInput(attrs={'size': 50}),
            'email': forms.TextInput(attrs={'size': 50}),
            'name': forms.TextInput(attrs={'size': 50}),
            'web_page': forms.TextInput(attrs={'size': 50}),
            'image_file': forms.FileInput(attrs={'class': 'fileinput'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Invalid email address")
        return email

    def clean(self):
        cleaned_data = super().clean()
        for field in self.Meta.fields:
            if field not in cleaned_data and self.fields[field].required and not self.errors.get(field):
                self.add_error(field, "This field is required")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(UserModelForm, self).__init__(*args, **kwargs)
        self.fields['role'].required = False
        self.fields['image_file'].required = False