from django.db import models
from django.core.validators import RegexValidator, EmailValidator
from django.utils.translation import gettext_lazy as _

class Person(models.Model):
    family = models.CharField(max_length=255, null=True, blank=True)
    given = models.CharField(max_length=255, null=True, blank=True)
    dropping_particle = models.CharField(max_length=255, null=True, blank=True)
    non_dropping_particle = models.CharField(max_length=255, null=True, blank=True)
    suffix = models.CharField(max_length=255, null=True, blank=True)
    comma_suffix = models.BooleanField(default=False)
    static_ordering = models.BooleanField(default=False)
    literal = models.CharField(max_length=255, null=True, blank=True)
    parse_names = models.BooleanField(default=False)
    orcid = models.CharField(
        max_length=19,
        validators=[
            RegexValidator(
                regex=r"^\d{4}-\d{4}-\d{4}-\d{4}$",
                message=_("Invalid ORCiD. Format should be: 0000-0000-0000-0000"),
            )
        ],
        null=True,
        blank=True,
        unique=True,
    )
    affiliation = models.CharField(max_length=255, null=True, blank=True)

    # Use a related name to handle multiple emails
    emails = models.ManyToManyField(
        'EmailAddress',
        related_name='persons',
        blank=True
    )

    def __str__(self):
        parts = [self.given, self.family]
        if self.suffix:
            parts.append(self.suffix)
        return ' '.join(part for part in parts if part)

    class Meta:
        verbose_name = "Person"
        verbose_name_plural = "People"
        # Unique constraint on combination of fields to avoid duplicate records
        constraints = [
            models.UniqueConstraint(
                fields=['family', 'given', 'orcid'],
                name='unique_person'
            )
        ]

class EmailAddress(models.Model):
    address = models.EmailField(
        validators=[EmailValidator(message=_("Enter a valid email address."))],
        unique=True
    )

    def __str__(self):
        return self.address

    class Meta:
        verbose_name = "Email Address"
        verbose_name_plural = "Email Addresses"
