import uuid

from django.db import models


class LocationZone(models.Model):
    """
    Canonical location hierarchy for Kata Wild.

    MVP purpose:
    - Store countries, regions, mountains, areas, corridors, habitats, and custom zones.
    - Support recursive parent/child location structure without hardcoding fixed levels.
    - Separate public-safe location labels from private/internal geography.

    Important architecture rule:
    LocationZone is not a frontend map label.
    It is canonical location context used later by monitoring points, observations,
    atlas outputs, research exports, and public-safe location display.

    Left for later:
    - Geometry validation.
    - Parent-cycle validation through a dedicated validator.
    - Public/private coordinate redaction policies.
    - GIS/PostGIS upgrade if needed.
    """

    class ZoneType(models.TextChoices):
        COUNTRY = "country", "Country"
        REGION = "region", "Region"
        AREA = "area", "Area"
        SUB_AREA = "sub_area", "Sub area"
        ZONE = "zone", "Zone"
        CORRIDOR = "corridor", "Corridor"
        HABITAT_AREA = "habitat_area", "Habitat area"
        RIVER_BASIN = "river_basin", "River basin"
        MOUNTAIN_SECTOR = "mountain_sector", "Mountain sector"
        CUSTOM = "custom", "Custom"

    class PrecisionLevel(models.TextChoices):
        EXACT = "exact", "Exact"
        APPROXIMATE = "approximate", "Approximate"
        GENERALIZED = "generalized", "Generalized"
        REGION_ONLY = "region_only", "Region only"
        HIDDEN = "hidden", "Hidden"

    class SensitivityLevel(models.TextChoices):
        NORMAL = "normal", "Normal"
        SENSITIVE = "sensitive", "Sensitive"
        HIGHLY_SENSITIVE = "highly_sensitive", "Highly sensitive"
        CRITICAL = "critical", "Critical"

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner"
        RESEARCH = "research", "Research"
        RESTRICTED = "restricted", "Restricted"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    parent_zone = models.ForeignKey(
        "locations.LocationZone",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="child_zones",
    )

    name_bs = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180, blank=True)

    zone_type = models.CharField(
        max_length=40,
        choices=ZoneType.choices,
        default=ZoneType.CUSTOM,
    )

    # Public labels are safe names for public pages, maps, and future APIs.
    public_label_bs = models.CharField(max_length=180, blank=True)
    public_label_en = models.CharField(max_length=180, blank=True)

    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    # JSON keeps MVP database simple while preserving future geometry direction.
    # Later we may move this to GIS fields if PostGIS becomes necessary.
    public_geometry = models.JSONField(blank=True, null=True)
    private_geometry = models.JSONField(blank=True, null=True)

    public_center_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    public_center_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    private_center_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    private_center_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )

    precision_level = models.CharField(
        max_length=30,
        choices=PrecisionLevel.choices,
        default=PrecisionLevel.GENERALIZED,
    )
    sensitivity_level = models.CharField(
        max_length=30,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.NORMAL,
    )
    visibility_level = models.CharField(
        max_length=30,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.PUBLIC,
    )

    is_public = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Location zone"
        verbose_name_plural = "Location zones"
        ordering = ["name_bs"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["zone_type"]),
            models.Index(fields=["visibility_level"]),
            models.Index(fields=["sensitivity_level"]),
            models.Index(fields=["is_public"]),
        ]

    def __str__(self):
        return self.name_bs