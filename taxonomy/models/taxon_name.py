import uuid

from django.db import models


class TaxonName(models.Model):
    """
    Canonical naming record for a Taxon.

    MVP purpose:
    - Store scientific names, Bosnian common names, English common names,
      local names, synonyms, and historical/deprecated names.
    - Preserve naming history without changing biological identity.

    Important architecture rule:
    Name is not identity.
    Taxon.code is the stable identity anchor.

    Left for later:
    - More advanced source tracking.
    - Validity windows for historical names.
    - Name-review workflow if taxonomy becomes research-grade.
    """

    class NameType(models.TextChoices):
        SCIENTIFIC_NAME = "scientific_name", "Scientific name"
        COMMON_NAME_BS = "common_name_bs", "Common name BS"
        COMMON_NAME_EN = "common_name_en", "Common name EN"
        LOCAL_NAME = "local_name", "Local name"
        HISTORICAL_NAME = "historical_name", "Historical name"
        GOVERNMENT_NAME = "government_name", "Government name"
        RESEARCH_NAME = "research_name", "Research name"
        SYNONYM = "synonym", "Synonym"
        DEPRECATED_NAME = "deprecated_name", "Deprecated name"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.CASCADE,
        related_name="names",
    )

    name = models.CharField(max_length=220)
    name_type = models.CharField(
        max_length=40,
        choices=NameType.choices,
        default=NameType.COMMON_NAME_BS,
    )

    language_code = models.CharField(max_length=12, blank=True)
    source = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)

    valid_from = models.DateField(blank=True, null=True)
    valid_to = models.DateField(blank=True, null=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["taxon__canonical_display_name_bs", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["taxon", "name", "name_type", "language_code"],
                name="unique_taxon_name_per_type_language",
            ),
        ]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["name_type"]),
            models.Index(fields=["language_code"]),
            models.Index(fields=["is_primary"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.taxon})"