# ingestion/models.py

from django.db.models import JSONField
from django.db import models
from django.contrib.gis.db import models as geomodels

import logging

logger = logging.getLogger(__name__)


class DatasetConfig(models.Model):
    dataset_name = models.CharField(max_length=255, unique=True)
    url = models.URLField()
    item_path = models.CharField(max_length=255)
    api_item = models.CharField(max_length=255, null=True, blank=True)  # Pattern for API item retrieval
    update_frequency = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'daily', 'weekly'
    last_updated = models.DateTimeField(null=True, blank=True)  # Track when it was last updated
    api_key = models.CharField(max_length=255, null=True, blank=True)  # For datasets that require authentication

    def __str__(self):
        return self.dataset_name

    @classmethod
    def create_dataset_config(cls, dataset_name, url, item_path, api_item, update_frequency=None, api_key=None):
        return cls.objects.create(
            dataset_name=dataset_name,
            url=url,
            item_path=item_path,
            api_item=api_item,
            update_frequency=update_frequency,
            api_key=api_key
        )


class Toponym(models.Model):
    """Represents a name which may apply to multiple places, along with its language and embeddings."""
    toponym = models.CharField(max_length=255)
    language = models.CharField(max_length=50)  # Use BCP 47 language tags
    is_romanised = models.BooleanField(default=False)  # Indicates if the name is in romanised form
    phonetic_embedding = models.JSONField(null=True, blank=True)  # Store G2P-PanPhon embeddings for the toponym
    semantic_embedding = models.JSONField(null=True, blank=True)  # Store mBERT embeddings for the toponym

    def __str__(self):
        return f"{self.toponym}@{self.language})"  # TODO: Include romanisation indicator in string representation - using BCP 47 language tags?

    class Meta:
        unique_together = ('toponym', 'language', 'is_romanised')

    @classmethod
    def create_toponym(cls, toponym, language, is_romanised=False, phonetic_embedding=None, semantic_embedding=None):
        toponym_instance, created = cls.objects.get_or_create(
            toponym=toponym,
            language=language,
            is_romanised=is_romanised,
            defaults={
                'phonetic_embedding': phonetic_embedding,
                'semantic_embedding': semantic_embedding
            }
        )

        # Trigger embedding generation if toponym was newly created
        # if created: #TODO
        #     generate_embeddings.delay(toponym_instance)

        return toponym_instance


class NPR(models.Model):
    """Normalised Place Record (NPR) representing a place with primary name, geometry, and other metadata."""
    source = models.ForeignKey(DatasetConfig, on_delete=models.CASCADE, related_name='nprs')
    item_id = models.CharField(max_length=255, null=True)  # id within the source dataset
    primary_name = models.CharField(max_length=255, null=True)  # Main name for the place
    geometry_point = geomodels.PointField(null=True, blank=True)  # For point geometries
    geometry_bbox = geomodels.PolygonField(null=True, blank=True)  # For bounding box geometries
    feature_classes = models.JSONField()  # Array of GeoNames feature classes
    lpf_feature = JSONField()  # Standard LPF feature in JSON format
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.primary_name or 'Unnamed Place'

    @classmethod
    def create_npr(cls, source, item_id, primary_name, geometry_point, geometry_bbox, feature_classes, lpf_feature):
        try:
            npr_instance = cls(
                source=source,
                item_id=item_id,
                primary_name=primary_name,
                geometry_point=geometry_point,
                geometry_bbox=geometry_bbox,
                feature_classes=feature_classes or [],
                lpf_feature=lpf_feature or {},
            )
            npr_instance.save()  # Save to the database
            return npr_instance  # Return the created instance
        except Exception as e:
            logger.error(f"Error saving NPR instance: {e}")
            return None  # Optionally return None or raise an error


class Attestation(models.Model):
    """Represents an attestation of a toponym for an NPR, with temporal attributes."""
    npr = models.ForeignKey(NPR, related_name='attestations', on_delete=models.CASCADE)
    toponym = models.ForeignKey(Toponym, related_name='attestations', on_delete=models.CASCADE)
    start = models.IntegerField(null=True, blank=True)
    end = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.toponym} for {self.npr} ({self.start or 'N/A'} - {self.end or 'N/A'})"

    class Meta:
        unique_together = ('npr', 'toponym', 'start', 'end')

    @classmethod
    def create_attestation(cls, npr, toponym, start=None, end=None):
        return cls.objects.create(
            npr=npr,
            toponym=toponym,
            start=start,
            end=end
        )
