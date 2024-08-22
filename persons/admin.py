from django.contrib import admin
from .models import Person, EmailAddress

class EmailAddressInline(admin.TabularInline):
    model = Person.emails.through
    extra = 1

class PersonAdmin(admin.ModelAdmin):
    list_display = (
        'family',
        'given',
        'orcid',
        'affiliation',
        'email_list',
    )
    search_fields = (
        'family',
        'given',
        'orcid',
        'emails__address',
    )
    filter_horizontal = ('emails',)
    inlines = [EmailAddressInline]  # Add this line to include the inline

    def email_list(self, obj):
        return ', '.join(email.address for email in obj.emails.all())
    email_list.short_description = 'Emails'

admin.site.register(Person, PersonAdmin)

class EmailAddressAdmin(admin.ModelAdmin):
    list_display = ('address',)

admin.site.register(EmailAddress, EmailAddressAdmin)
