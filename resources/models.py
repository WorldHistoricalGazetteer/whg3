import json
from functools import reduce

from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.core.cache import cache
from django.core.validators import MaxValueValidator
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.functional import cached_property

from areas.models import Area

User = get_user_model()
from django.contrib.postgres.fields import ArrayField
from main.choices import *
from utils.csl_citation_formatter import csl_citation

from multiselectfield import MultiSelectField


def resource_file_path(instance, filename):
    # upload to MEDIA_ROOT/resources/<id>_<filename>
    return 'resources/{0}'.format(filename)


class Resource(models.Model):
    create_date = models.DateTimeField(null=True, auto_now_add=True)
    pub_date = models.DateTimeField(null=False)
    owner = models.ForeignKey(
        User, related_name='resources', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=False)
    # [lessonplan | syllabus]
    type = models.CharField(max_length=12, null=False, choices=RESOURCE_TYPES)
    description = models.TextField(max_length=2044, null=False)
    subjects = models.CharField(max_length=2044, null=False)
    gradelevels = ArrayField(models.CharField(max_length=24, blank=True))
    keywords = ArrayField(models.CharField(max_length=24, null=False))
    authors = models.CharField(max_length=500, null=False)
    contact = models.CharField(max_length=500, null=True, blank=True)
    webpage = models.URLField(null=True, blank=True)
    public = models.BooleanField(default=False)
    doi = models.BooleanField(default=False, help_text="Indicates if a DOI is associated with this resource")
    featured = models.IntegerField(null=True, blank=True)

    regions = models.ManyToManyField('areas.Area', related_name='resources', blank=True)

    # [uploaded | published]
    status = models.CharField(
        max_length=12, null=True, blank=True, choices=RESOURCE_STATUS, default='uploaded')

    def __str__(self):
        return self.title
        # return '%d: %s' % (self.id, self.label)

    def title_length(self):
        return -len(self.title)

    # @property
    # def region_ids(self):
    #     # Ensure `regions` is converted to a list of integers, handling potential comma-separated strings.
    #     if isinstance(self.regions, str):
    #         return [int(region_id.strip()) for region_id in self.regions.split(',') if region_id.strip().isdigit()]
    #     elif isinstance(self.regions, list):
    #         return [int(region_id) for region_id in self.regions if isinstance(region_id, int)]
    #     return []

    @cached_property
    def region_ids(self):
        # Use prefetched regions if available
        if hasattr(self, '_prefetched_objects_cache') and 'regions' in self._prefetched_objects_cache:
            return [area.id for area in self._prefetched_objects_cache['regions']]
        return list(self.regions.values_list('id', flat=True))

    @cached_property
    def region_ids_csv(self):
        ids = self.region_ids
        if not ids:
            # cached predefined areas
            predefined_ids = cache.get('predefined_area_ids')
            if predefined_ids is None:
                predefined_ids = list(
                    Area.objects.filter(type="predefined").values_list('id', flat=True)
                )
                cache.set('predefined_area_ids', predefined_ids, 3600)  # 1 hour cache
            ids = predefined_ids
        return ','.join(map(str, ids))

    @property
    def region_titles_csv(self):
        region_titles = [area.title for area in self.regions.all() if area is not None]
        return ', '.join(map(str, region_titles)) if region_titles else '-'

    @property
    def citation_csl(self):
        return csl_citation(self)

    @property
    def bbox(self):
        # Fetch bounding boxes for the regions associated with this resource
        extent = self.regions.aggregate(Extent("bbox"))["bbox__extent"]

        return Polygon.from_bbox(extent) if extent else None

    class Meta:
        managed = True
        db_table = 'resources'
        indexes = [
            models.Index(fields=['public'], name='resources_public_idx'),
            models.Index(fields=['featured'], name='resources_featured_idx', condition=Q(featured__isnull=False)),
        ]


class ResourceFile(models.Model):
    resource = models.ForeignKey(Resource, default=None, on_delete=models.CASCADE)
    file = models.FileField(upload_to=resource_file_path)
    filetype = models.CharField(max_length=12, null=False, blank=False,
                                choices=RESOURCEFILE_ROLE, default='primary')

    # def __str__(self):
    #   return self.file

    class Meta:
        managed = True
        db_table = 'resource_file'


class ResourceImage(models.Model):
    resource = models.ForeignKey(Resource, default=None, on_delete=models.CASCADE)
    image = models.FileField(upload_to=resource_file_path)

    # def __str__(self):
    #   return self.image

    class Meta:
        managed = True
        db_table = 'resource_image'
