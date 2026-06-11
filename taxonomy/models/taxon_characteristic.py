import uuid

from django.db import models


class TaxonCharacteristic(models.Model):
    """
    Canonical biological or ecological characteristic for a Taxon.

    MVP purpose:
    - Store reusable facts about a taxon, such as diet, activity pattern, lifespan,
      breeding season, habitat preference, coloration, or identification notes.
    - Keep general taxon facts separate from observations.

    Important architecture rule:
    TaxonCharacteristic describes the taxon generally.
    Specific observed behavior belongs later to Observation, not here.

    Left for later:
    - Source quality review.
    - Stronger typed values per characteristic type.
    - Public-safe selector rules for sensitive characteristics.
    """

    class CharacteristicType(models.TextChoices):
        AVERAGE_WEIGHT = "average_weight", "Average weight"
        MINIMUM_WEIGHT = "minimum_weight", "Minimum weight"
        MAXIMUM_WEIGHT = "maximum_weight", "Maximum weight"
        AVERAGE_LENGTH = "average_length", "Average length"
        HEIGHT = "height", "Height"
        WINGSPAN = "wingspan", "Wingspan"
        COLORATION = "coloration", "Coloration"

        LIFESPAN = "lifespan", "Lifespan"
        GESTATION_PERIOD = "gestation_period", "Gestation period"
        OFFSPRING_COUNT = "offspring_count", "Offspring count"
        BREEDING_SEASON = "breeding_season", "Breeding season"
        SEXUAL_MATURITY = "sexual_maturity", "Sexual maturity"

        ACTIVITY_PATTERN = "activity_pattern", "Activity pattern"
        SOCIAL_BEHAVIOR = "social_behavior", "Social behavior"
        MIGRATION_BEHAVIOR = "migration_behavior", "Migration behavior"
        TERRITORIAL_BEHAVIOR = "territorial_behavior", "Territorial behavior"

        DIET = "diet", "Diet"
        PREDATORS = "predators", "Predators"
        PREY = "prey", "Prey"
        PREFERRED_HABITATS = "preferred_habitats", "Preferred habitats"
        ELEVATION_RANGE = "elevation_range", "Elevation range"
        CLIMATE_PREFERENCES = "climate_preferences", "Climate preferences"

        THREATS = "threats", "Threats"
        PROTECTION_MEASURES = "protection_measures", "Protection measures"

        IDENTIFICATION_NOTES = "identification_notes", "Identification notes"
        TAXONOMIC_NOTES = "taxonomic_notes", "Taxonomic notes"
        KNOWN_VARIATIONS = "known_variations", "Known variations"

        OTHER = "other", "Other"

    class ConfidenceLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        VERIFIED = "verified", "Verified"
        UNKNOWN = "unknown", "Unknown"

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner"
        RESEARCH = "research", "Research"
        RESTRICTED = "restricted", "Restricted"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.CASCADE,
        related_name="characteristics",
    )

    characteristic_type = models.CharField(
        max_length=60,
        choices=CharacteristicType.choices,
        default=CharacteristicType.OTHER,
    )

    value_text_bs = models.TextField(blank=True)
    value_text_en = models.TextField(blank=True)

    value_number = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        blank=True,
        null=True,
    )
    unit = models.CharField(max_length=40, blank=True)

    source = models.CharField(max_length=255, blank=True)
    confidence_level = models.CharField(
        max_length=30,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.UNKNOWN,
    )

    visibility_level = models.CharField(
        max_length=30,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.PUBLIC,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Taxon characteristic"
        verbose_name_plural = "Taxon characteristics"
        ordering = ["taxon__canonical_display_name_bs", "characteristic_type"]
        indexes = [
            models.Index(fields=["characteristic_type"]),
            models.Index(fields=["confidence_level"]),
            models.Index(fields=["visibility_level"]),
        ]

    def __str__(self):
        return f"{self.taxon} - {self.get_characteristic_type_display()}"