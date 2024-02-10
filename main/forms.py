from django import forms
from django.conf import settings
from django.db import models
from django.utils.safestring import mark_safe

from main.models import Comment
from main.choices import COMMENT_TAGS, COMMENT_TAGS_REVIEW
from bootstrap_modal_forms.forms import BSModalForm
from captcha.fields import CaptchaField
import sys

from django import forms
from .models import Announcement

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['headline', 'content', 'link', 'active']


class ContactForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'size': 50}),
        required=True)
    from_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'size': 50}),
        required=True,
        label="Your email address ")
    subject = forms.CharField(
        widget=forms.TextInput(attrs={'size': 50}),
        required=True)
    message = forms.CharField(widget=forms.Textarea(attrs={'cols': 50, 'rows': 5}), required=True)
    username = forms.CharField(widget=forms.HiddenInput(), required=False)
    captcha = CaptchaField()

    def clean_captcha(self):
        print('in clean_captcha')
        if settings.TESTING:
            # Bypass CAPTCHA validation
            return self.cleaned_data.get('captcha')

    # def clean_captcha(self):
    #     print('in clean_captcha')
    #     print('test in sys.argv?', 'test' in sys.argv)
    #     captcha = self.cleaned_data.get('captcha')
    #
    #     # Skip captcha validation if 'test' is in sys.argv
    #     if 'test' in sys.argv:
    #         print('test in sys.argv, skipping captcha validation')
    #         return captcha
    #
    #     # Your custom captcha validation logic (if any) goes here
    #     # If there's no additional validation needed, just return the captcha value
    #     return captcha


class CommentModalForm(BSModalForm):
    class Meta:
        model = Comment
        # all fields: user, place_id, tag, note, created
        fields = ['tag', 'note','place_id']
        hidden_fields = ['created']
        exclude = ['user','place_id']
        widgets = {
            'place_id': forms.TextInput(),
            'tag': forms.RadioSelect(choices=COMMENT_TAGS, attrs={'class':'no-bullet'}),
            'note': forms.Textarea(attrs={
                'rows':2,'cols': 40,'class':'textarea'})
        }
        
    def __init__(self, *args, **kwargs):
        super(CommentModalForm, self).__init__(*args, **kwargs)  
        self.fields['tag'].label = "Issue"
        if '/def' in kwargs['initial']['next']:
            self.fields['tag'].choices = COMMENT_TAGS_REVIEW
