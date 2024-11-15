from django.contrib import admin

from areas.models import Area
# Register your models here.
from .models import Resource, ResourceFile, ResourceImage

class ResourceFileAdmin(admin.StackedInline):
    model = ResourceFile

class ResourceImageAdmin(admin.StackedInline):
    model = ResourceImage

# pub_date, owner, title, type, description, subjects, gradelevels, keywords, authors,
# contact, webpage, public, featured, regions, status

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    fields = ('pub_date','owner','title','authors','description','keywords',
              'type','subjects','gradelevels', 'public', 'featured', 'status',
              'regions')
    list_display = ('title', 'pub_date', 'authors', 'gradelevels', 'type', 'featured')
    list_filters = ('gradelevels', 'authors')
    # date_hierarchy = 'pub_date'

    # Dynamically populate the regions field in the admin form with Areas where type == "predefined"
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "regions":
            kwargs["queryset"] = Area.objects.filter(type="predefined")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    inlines = [ResourceFileAdmin, ResourceImageAdmin]

    class Meta:
       model = Resource


@admin.register(ResourceFile)
class ResourceFileAdmin(admin.ModelAdmin):
    pass

@admin.register(ResourceImage)
class ResourceImageAdmin(admin.ModelAdmin):
    pass
