import uuid

from django.core.exceptions import ValidationError
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
        
    def clean(self):
        """
        Validate location-zone hierarchy and coordinate consistency.

        MVP purpose:
        - Prevent a zone from becoming its own parent.
        - Prevent half-stored public/private center coordinates.
        - Keep public visibility flags aligned with restricted/sensitive location data.

        Architecture rule:
        - LocationZone is canonical location context, not a frontend map label.
        - Private geometry and private coordinates are protected scientific data.
        - Public location output must use public-safe labels/geometry later through selectors.

        Left for later:
        - Dedicated recursive parent-cycle validator.
        - GIS/PostGIS geometry validation.
        - Public/private coordinate redaction policies and audited access.
        """

        super().clean()

        errors = {}

        if self.pk and self.parent_zone_id == self.pk:
            errors["parent_zone"] = "A location zone cannot be its own parent."

        has_public_latitude = self.public_center_latitude is not None
        has_public_longitude = self.public_center_longitude is not None

        if has_public_latitude != has_public_longitude:
            errors["public_center_latitude"] = (
                "Public center latitude and longitude must be set together."
            )
            errors["public_center_longitude"] = (
                "Public center latitude and longitude must be set together."
            )

        has_private_latitude = self.private_center_latitude is not None
        has_private_longitude = self.private_center_longitude is not None

        if has_private_latitude != has_private_longitude:
            errors["private_center_latitude"] = (
                "Private center latitude and longitude must be set together."
            )
            errors["private_center_longitude"] = (
                "Private center latitude and longitude must be set together."
            )

        if self.is_public and self.visibility_level == self.VisibilityLevel.RESTRICTED:
            errors["is_public"] = (
                "Restricted location zones cannot be marked public."
            )

        if self.is_public and self.precision_level == self.PrecisionLevel.HIDDEN:
            errors["precision_level"] = (
                "Public location zones cannot use hidden precision."
            )

        if (
            self.is_public
            and self.sensitivity_level
            in {
                self.SensitivityLevel.HIGHLY_SENSITIVE,
                self.SensitivityLevel.CRITICAL,
            }
        ):
            errors["sensitivity_level"] = (
                "Highly sensitive or critical location zones cannot be marked public."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name_bs