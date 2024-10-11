# ingestion/models.py

from django.db.models import JSONField
from django.db import models

import logging

logger = logging.getLogger(__name__)


class Toponym(models.Model):
    """Represents a name which may apply to multiple places, along with its language and embeddings."""
    toponym = models.CharField(max_length=255)
    language = models.CharField(max_length=50, null=True, blank=True)  # Use BCP 47 language tags
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
    source = models.CharField(max_length=255)  # Source dataset name
    item_id = models.CharField(max_length=255, null=True)  # id within the source dataset
    primary_name = models.CharField(max_length=255, null=True)  # Main name for the place
    geometry_point = models.JSONField(null=True, blank=True)  # For point geometries
    geometry_bbox = models.JSONField(null=True, blank=True)  # For bounding box geometries
    feature_classes = models.JSONField(null=True, blank=True)  # Array of GeoNames feature classes
    ccodes = models.JSONField(null=True, blank=True)  # Modern country codes associated with the place geometry
    lpf_feature = JSONField(null=True, blank=True)  # Standard LPF feature in JSON format
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.primary_name or 'Unnamed Place'

    @classmethod
    def create_npr(cls, **kwargs):
        source = kwargs.get('source')
        item_id = kwargs.get('item_id')

        # Check if an instance already exists
        npr_instance = cls.objects.filter(source=source, item_id=item_id).first()
        if npr_instance:
            return npr_instance

        try:
            # Create and save a new instance
            npr_instance = cls(**kwargs)
            npr_instance.save()
            return npr_instance
        except Exception as e:
            logger.error(f"Error saving NPR instance: {e}")
            return None  # Optionally return None or raise an error


class Attestation(models.Model):
    """Represents an attestation of a toponym for an NPR, with temporal attributes."""
    npr = models.ForeignKey(NPR, related_name='attestations', on_delete=models.CASCADE)
    toponym = models.ForeignKey(Toponym, related_name='attestations', on_delete=models.CASCADE)
    start = models.IntegerField(null=True, blank=True)
    end = models.IntegerField(null=True, blank=True)
    geoname_id = models.CharField(max_length=255, blank=True, null=True)
    geoname_toponym_id = models.CharField(max_length=255, blank=True, null=True)
    is_preferred = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.toponym} for {self.npr} ({self.start or 'N/A'} - {self.end or 'N/A'})"

    class Meta:
        unique_together = ('npr', 'toponym', 'start', 'end')

    @classmethod
    def create_attestation(cls, npr, toponym, **kwargs):
        # Create an attestation using the provided npr, toponym, and any additional keyword arguments
        return cls.objects.create(
            npr=npr,
            toponym=toponym,
            **kwargs  # Unpack the keyword arguments to pass them to the model
        )
