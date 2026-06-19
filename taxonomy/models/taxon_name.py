import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


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
                fields=["taxon", "name_type", "language_code"],
                condition=Q(is_primary=True),
                name="unique_primary_taxon_name_per_type_language",
            ),
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

    def clean(self):
        """
        Validate taxon naming consistency.

        MVP purpose:
        - Keep TaxonName records usable for bilingual/public/scientific display.
        - Prevent impossible historical validity ranges.
        - Keep primary names tied to clear, current naming records.

        Architecture rule:
        - Name is not identity.
        - Taxon.code is the stable biological identity anchor.
        - TaxonName stores labels, aliases, synonyms, and naming history only.

        Left for later:
        - Dedicated taxonomy naming workflow.
        - Source authority ranking.
        - Multi-language/public selector rules.
        """

        super().clean()

        errors = {}

        if self.valid_from and self.valid_to:
            if self.valid_from > self.valid_to:
                errors["valid_to"] = (
                    "Taxon name valid_to cannot be earlier than valid_from."
                )

        language_required_types = {
            self.NameType.COMMON_NAME_BS,
            self.NameType.COMMON_NAME_EN,
            self.NameType.LOCAL_NAME,
            self.NameType.GOVERNMENT_NAME,
            self.NameType.RESEARCH_NAME,
        }

        if self.name_type in language_required_types and not self.language_code:
            errors["language_code"] = (
                "Common, local, government, and research names require language_code."
            )

        if self.name_type == self.NameType.COMMON_NAME_BS and self.language_code not in {
            "",
            "bs",
        }:
            errors["language_code"] = (
                "Bosnian common names must use language_code 'bs'."
            )

        if self.name_type == self.NameType.COMMON_NAME_EN and self.language_code not in {
            "",
            "en",
        }:
            errors["language_code"] = (
                "English common names must use language_code 'en'."
            )

        if self.is_primary and self.name_type in {
            self.NameType.SYNONYM,
            self.NameType.DEPRECATED_NAME,
            self.NameType.HISTORICAL_NAME,
        }:
            errors["is_primary"] = (
                "Synonym, deprecated, or historical names cannot be primary names."
            )

        if self.is_primary and self.valid_to:
            errors["is_primary"] = (
                "Names with valid_to set cannot be primary names."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.taxon})"