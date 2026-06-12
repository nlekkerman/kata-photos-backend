from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class ObservationTaxon(models.Model):
    """
    Verified or reviewable taxon identity connected to an Observation.

    MVP purpose:
    - Store the biological identity used by the scientific observation.
    - Allow uncertain or incomplete identification.
    - Preserve confidence, life stage, sex, count range, and behavior notes.

    Important architecture rule:
    Taxon is canonical biological identity truth.
    This model records the taxon interpretation for this observation.

    Left for later:
    - Multiple-reviewer identification workflow.
    - Revision history for changed identifications.
    - Expert review and AI-suggestion comparison.
    """

    class IdentificationStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        POSSIBLE = "possible", "Possible"
        LIKELY = "likely", "Likely"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class ConfidenceLevel(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CERTAIN = "certain", "Certain"

    class LifeStage(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        JUVENILE = "juvenile", "Juvenile"
        SUBADULT = "subadult", "Subadult"
        ADULT = "adult", "Adult"
        OLD = "old", "Old"

    class Sex(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        MIXED = "mixed", "Mixed"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    observation = models.ForeignKey(
        "observations.Observation",
        on_delete=models.CASCADE,
        related_name="taxon_links",
    )

    taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.PROTECT,
        related_name="observation_links",
        blank=True,
        null=True,
        help_text="Canonical taxon identity. Can be blank for unknown observations if needed.",
    )

    identification_status = models.CharField(
        max_length=40,
        choices=IdentificationStatus.choices,
        default=IdentificationStatus.UNKNOWN,
        db_index=True,
    )

    confidence_level = models.CharField(
        max_length=40,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.UNKNOWN,
        db_index=True,
    )

    life_stage = models.CharField(
        max_length=40,
        choices=LifeStage.choices,
        default=LifeStage.UNKNOWN,
        blank=True,
    )

    sex = models.CharField(
        max_length=40,
        choices=Sex.choices,
        default=Sex.UNKNOWN,
        blank=True,
    )

    count_min = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="Minimum observed count, if known.",
    )

    count_max = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum observed count, if known.",
    )

    behavior_notes_bs = models.TextField(
        blank=True,
        help_text="Bosnian behavior notes for this taxon in the observation.",
    )

    behavior_notes_en = models.TextField(
        blank=True,
        help_text="English behavior notes for this taxon in the observation.",
    )

    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="identified_observation_taxa",
        blank=True,
        null=True,
    )

    identified_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when this identification was made or confirmed.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["observation", "taxon_id", "-confidence_level"]
        indexes = [
            models.Index(fields=["identification_status", "confidence_level"]),
            models.Index(fields=["taxon", "identification_status"]),
        ]

    def __str__(self):
        if self.taxon:
            return f"{self.observation.code} - {self.taxon}"
        return f"{self.observation.code} - Unknown taxon"