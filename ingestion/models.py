# ingestion/models.py

from django.db.models import JSONField, UniqueConstraint
from django.db import models

import logging

from ingestion.transformers import isocodes

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
                'semantic_embedding': semantic_embedding,
            }
        )

        # Trigger embedding generation if toponym was newly created
        # if created: #TODO
        #     generate_embeddings.delay(toponym_instance)

        return toponym_instance


class ToponymLookup(models.Model):
    """Links toponyms with their source toponym IDs."""
    toponym = models.ForeignKey('Toponym', on_delete=models.CASCADE, related_name='lookups')
    source_toponym_id = models.CharField(max_length=255, null=True, blank=True)  # ID from the source dataset

    def __str__(self):
        return f"{self.toponym} (Source ID: {self.source_toponym_id})"

    class Meta:
        unique_together = ('toponym', 'source_toponym_id')


class NPR(models.Model):
    """Normalised Place Record (NPR) representing a place with primary name, geometry, and other metadata."""
    source = models.CharField(max_length=255)  # Source dataset name
    item_id = models.CharField(max_length=255, null=True)  # id within the source dataset
    primary_name = models.CharField(max_length=255, null=True)  # Main name for the place
    latitude = models.FloatField(null=True, blank=True)  # Latitude of the place
    longitude = models.FloatField(null=True, blank=True)  # Longitude of the place
    geometry_bbox = models.JSONField(null=True, blank=True)  # For bounding box geometries
    feature_classes = models.JSONField(null=True, blank=True)  # Array of GeoNames feature classes
    ccodes = models.JSONField(null=True, blank=True)  # Modern country codes associated with the place geometry
    lpf_feature = JSONField(null=True, blank=True)  # Standard LPF feature in JSON format
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('source', 'item_id')

    def __str__(self):
        return self.primary_name or 'Unnamed Place'

    @classmethod
    def create_or_update(cls, source, item_id, **kwargs):
        """
        Retrieve an NPR instance by source and item_id. If it exists, update it with the provided kwargs.
        If it does not exist, create a new NPR instance with the provided data.
        """
        try:
            # Try to find the NPR instance
            npr_instance, created = cls.objects.get_or_create(source=source, item_id=item_id)

            if created:
                # If the instance was newly created, set additional attributes
                for key, value in kwargs.items():
                    setattr(npr_instance, key, value)
                npr_instance.save()
                logger.info(f"Created new NPR instance with item_id: {item_id}")
            else:
                # If the instance already exists, update it with any new data
                updated = False
                for key, value in kwargs.items():
                    if key == 'feature_classes' and value:
                        # Extend feature_classes list if it already exists
                        if isinstance(npr_instance.feature_classes, list):
                            new_classes = set(npr_instance.feature_classes) | set(value)
                            if npr_instance.feature_classes != list(new_classes):
                                npr_instance.feature_classes = list(new_classes)
                                updated = True
                        else:
                            npr_instance.feature_classes = value
                            updated = True
                    elif getattr(npr_instance, key) != value:
                        setattr(npr_instance, key, value)
                        updated = True
                if updated:
                    npr_instance.save()
                    logger.info(f"Updated existing NPR instance with item_id: {item_id}")

            return npr_instance

        except Exception as e:
            logger.error(f"Error processing NPR instance: {e}")
            return None

    @classmethod
    def update_primary_names(cls):
        """
        Iterate over all NPR instances and update their primary_name field using the preferred toponym.
        """
        for npr in cls.objects.all():
            # Get Attestations which have npr_item_id same as item_id of NPR
            preferred_attestation = Attestation.objects.filter(npr_item_id=npr.item_id, is_preferred=True).first()
            # logger.debug(f"Preferred attestation for NPR with item_id: {npr.item_id} - {preferred_attestation}")

            if preferred_attestation and preferred_attestation.toponym:
                # Update primary_name with the toponym associated with the preferred attestation
                npr.primary_name = preferred_attestation.toponym.toponym
                npr.save()
            #     logger.info(f"Updated NPR primary_name to '{npr.primary_name}' for item_id: {npr.item_id}")
            # else:
            #     logger.info(f"No preferred attestation or toponym found for NPR with item_id: {npr.item_id}")

    @classmethod
    def compute_ccodes(cls):
        """
        Iterate over all NPR instances and compute their ccodes field using the associated geometry.
        """
        for npr in cls.objects.all():
            if not npr.ccodes and npr.latitude and npr.longitude:
                npr.ccodes = isocodes([{'type': 'Point', 'coordinates': [npr.longitude, npr.latitude]}])
                npr.save()


class Attestation(models.Model):
    """Represents an attestation of a toponym for an NPR, with temporal attributes."""
    source = models.CharField(max_length=255)  # Source dataset name
    npr = models.ForeignKey(NPR, related_name='attestations', on_delete=models.CASCADE)
    toponym = models.ForeignKey(Toponym, related_name='attestations', on_delete=models.CASCADE, null=True, blank=True)
    start = models.IntegerField(null=True, blank=True)
    end = models.IntegerField(null=True, blank=True)
    npr_item_id = models.CharField(max_length=255, blank=True, null=True)
    source_toponym_id = models.CharField(max_length=255, blank=True, null=True)
    is_preferred = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.toponym} for {self.npr} ({self.start or 'N/A'} - {self.end or 'N/A'})"

    class Meta:
        constraints = [
            UniqueConstraint(fields=['npr', 'toponym', 'start', 'end'], name='unique_npr_toponym_time'),
            UniqueConstraint(fields=['npr', 'source_toponym_id', 'start', 'end'], name='unique_npr_source_toponym')
        ]

    @classmethod
    def create_or_update_attestation(cls, npr, **kwargs):
        """
        Create or update an attestation. If an attestation with the given source_toponym_id exists, update it.
        Otherwise, create a new attestation.
        """
        source_toponym_id = kwargs.get('source_toponym_id')

        try:
            if source_toponym_id:
                # Check if an attestation with this source_toponym_id exists
                attestation = cls.objects.filter(source_toponym_id=source_toponym_id).first()
                if attestation:
                    # If it exists, update the attestation with the provided kwargs
                    updated = False
                    for key, value in kwargs.items():
                        if getattr(attestation, key) != value:
                            setattr(attestation, key, value)
                            updated = True
                    if updated:
                        attestation.save()
                        logger.info(f"Updated attestation with source_toponym_id: {source_toponym_id}")
                    return attestation

            # If no existing attestation was found, create a new one
            attestation = cls.objects.create(
                npr=npr,
                **kwargs  # Unpack keyword arguments to pass them to the model
            )
            logger.info(f"Created new attestation with source_toponym_id: {source_toponym_id}")
            return attestation

        except Exception as e:
            logger.error(f"Error creating/updating attestation: {e}")
            return None
