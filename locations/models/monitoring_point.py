import uuid

from django.core.exceptions import ValidationError
from django.db import models


class MonitoringPoint(models.Model):
    """
    Permanent scientific monitoring location.

    MVP purpose:
    - Store fixed points where monitoring can happen over time.
    - Connect monitoring work to a project, location zone, and habitat.
    - Prepare future camera deployments and observations.

    Important architecture rule:
    A MonitoringPoint is not a camera and not a disposable map pin.
    Monitoring points do not move. If the physical monitored place changes,
    create a new monitoring point and preserve history.

    Left for later:
    - Coordinate validation.
    - Monitoring point retirement service.
    - Coordinate access policies and audit for private coordinate reads.
    - CameraDeployment relationship in the monitoring app.
    """

    class PublicLocationPrecision(models.TextChoices):
        EXACT = "exact", "Exact"
        APPROXIMATE = "approximate", "Approximate"
        GENERALIZED = "generalized", "Generalized"
        ZONE_ONLY = "zone_only", "Zone only"
        HIDDEN = "hidden", "Hidden"

    class SensitivityLevel(models.TextChoices):
        NORMAL = "normal", "Normal"
        SENSITIVE = "sensitive", "Sensitive"
        HIGHLY_SENSITIVE = "highly_sensitive", "Highly sensitive"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        RETIRED = "retired", "Retired"
        ARCHIVED = "archived", "Archived"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="monitoring_points",
    )
    location_zone = models.ForeignKey(
        "locations.LocationZone",
        on_delete=models.PROTECT,
        related_name="monitoring_points",
    )
    primary_habitat = models.ForeignKey(
        "locations.Habitat",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="monitoring_points",
    )

    name_bs = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180, blank=True)

    purpose = models.TextField(blank=True)

    # Private coordinates are protected scientific data.
    # Public APIs must not expose these later without policy-controlled redaction.
    private_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    private_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )

    elevation_meters = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
    )

    public_location_label_bs = models.CharField(max_length=180, blank=True)
    public_location_label_en = models.CharField(max_length=180, blank=True)

    public_location_precision = models.CharField(
        max_length=30,
        choices=PublicLocationPrecision.choices,
        default=PublicLocationPrecision.GENERALIZED,
    )
    sensitivity_level = models.CharField(
        max_length=30,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.NORMAL,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNED,
    )

    started_at = models.DateField(blank=True, null=True)
    retired_at = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Monitoring point"
        verbose_name_plural = "Monitoring points"
        ordering = ["project__name_bs", "name_bs"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["location_zone", "status"]),
            models.Index(fields=["primary_habitat"]),
            models.Index(fields=["sensitivity_level"]),
        ]

    def clean(self):
        """
        Validate monitoring point lifecycle and private coordinate consistency.

        MVP purpose:
        - Keep monitoring points as stable scientific places.
        - Prevent impossible lifecycle dates.
        - Prevent half-stored private coordinates that break mapping and redaction logic.

        Architecture rule:
        - MonitoringPoint is a permanent scientific monitoring place.
        - MonitoringPoint is not a camera and should not be moved as camera hardware moves.
        - Private coordinates are protected scientific data and must only be exposed
          later through policy-controlled selectors.

        Left for later:
        - Dedicated monitoring point correction/retirement service.
        - Public-safe and workspace-safe selectors for coordinate redaction.
        - Audit logging for private coordinate reads.
        """

        super().clean()

        errors = {}

        if self.started_at and self.retired_at:
            if self.started_at > self.retired_at:
                errors["retired_at"] = (
                    "Monitoring point retired date cannot be earlier than started date."
                )

        has_latitude = self.private_latitude is not None
        has_longitude = self.private_longitude is not None

        if has_latitude != has_longitude:
            errors["private_latitude"] = (
                "Private latitude and private longitude must be set together."
            )
            errors["private_longitude"] = (
                "Private latitude and private longitude must be set together."
            )

        if self.status == self.Status.RETIRED and not self.retired_at:
            errors["retired_at"] = (
                "Retired monitoring points must have retired_at set."
            )

        if self.retired_at and self.status not in {
            self.Status.RETIRED,
            self.Status.ARCHIVED,
        }:
            errors["status"] = (
                "Only retired or archived monitoring points can have retired_at set."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name_bs