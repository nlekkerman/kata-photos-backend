import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Observation(models.Model):
    """
    Canonical scientific truth record for Kata Wild.

    MVP purpose:
    - Store the verified/reviewable occurrence of something observed in nature.
    - Connect scientific truth to project, place, monitoring context, camera deployment,
      evidence, taxon identification, visibility, and sensitivity.
    - Keep Evidence as supporting proof, not final truth.

    Important architecture rule:
    Observation is the scientific truth spine.
    Evidence supports Observation but does not replace Observation.

    Left for later:
    - Full revision/history model.
    - Verification service.
    - Publication workflow.
    - Sensitivity/redaction policy.
    - Public-safe selectors and APIs.
    - Audit logging for verification, publication, and sensitive access.
    """

    class ObservationType(models.TextChoices):
        CAMERA_TRAP = "camera_trap", "Camera trap"
        DIRECT_SIGHTING = "direct_sighting", "Direct sighting"
        TRACK_OR_SIGN = "track_or_sign", "Track or sign"
        AUDIO = "audio", "Audio"
        DRONE = "drone", "Drone"
        IMPORTED = "imported", "Imported"
        UNKNOWN = "unknown", "Unknown"

    class ObservationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "In review"
        VERIFIED = "verified", "Verified"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class VerificationStatus(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        REVIEW_NEEDED = "review_needed", "Review needed"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        UNCERTAIN = "uncertain", "Uncertain"

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

    class PublicLocationPrecision(models.TextChoices):
        NONE = "none", "No public location"
        REGION = "region", "Region only"
        LOCATION_ZONE = "location_zone", "Location zone"
        HABITAT = "habitat", "Habitat"
        MONITORING_POINT_GENERALIZED = (
            "monitoring_point_generalized",
            "Monitoring point generalized",
        )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(
        max_length=80,
        unique=True,
        db_index=True,
        help_text="Stable observation code, for example OBS-PLJ-001.",
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="observations",
        help_text="Project that owns this scientific observation.",
    )

    observation_type = models.CharField(
        max_length=40,
        choices=ObservationType.choices,
        default=ObservationType.CAMERA_TRAP,
        db_index=True,
    )

    observation_status = models.CharField(
        max_length=40,
        choices=ObservationStatus.choices,
        default=ObservationStatus.DRAFT,
        db_index=True,
    )

    verification_status = models.CharField(
        max_length=40,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNREVIEWED,
        db_index=True,
    )

    recorded_at = models.DateTimeField(
        db_index=True,
        help_text="Main timestamp when the observation was recorded or captured.",
    )

    observed_started_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional start time when the observed event began.",
    )

    observed_ended_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional end time when the observed event ended.",
    )

    monitoring_point = models.ForeignKey(
        "locations.MonitoringPoint",
        on_delete=models.PROTECT,
        related_name="observations",
        blank=True,
        null=True,
        help_text="Permanent monitoring point linked to this observation, if applicable.",
    )

    location_zone = models.ForeignKey(
        "locations.LocationZone",
        on_delete=models.PROTECT,
        related_name="observations",
        blank=True,
        null=True,
        help_text="General location zone for this observation.",
    )

    habitat = models.ForeignKey(
        "locations.Habitat",
        on_delete=models.PROTECT,
        related_name="observations",
        blank=True,
        null=True,
        help_text="Habitat context for this observation, if known.",
    )

    camera_deployment = models.ForeignKey(
        "monitoring.CameraDeployment",
        on_delete=models.PROTECT,
        related_name="observations",
        blank=True,
        null=True,
        help_text="Camera deployment context if this observation came from a deployed camera.",
    )

    sensitivity_level = models.CharField(
        max_length=40,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.NORMAL,
        db_index=True,
        help_text="Conservation/privacy risk level. Sensitive data must be protected later by policy.",
    )

    visibility_level = models.CharField(
        max_length=40,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.RESTRICTED,
        db_index=True,
        help_text="Audience-level visibility. Public exposure still requires safe selectors later.",
    )

    public_location_label_bs = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bosnian public-safe location label. Do not put exact coordinates here.",
    )

    public_location_label_en = models.CharField(
        max_length=255,
        blank=True,
        help_text="English public-safe location label. Do not put exact coordinates here.",
    )

    public_location_precision = models.CharField(
        max_length=60,
        choices=PublicLocationPrecision.choices,
        default=PublicLocationPrecision.NONE,
        help_text="Controls how precise public location can be later.",
    )

    notes_public_bs = models.TextField(
        blank=True,
        help_text="Bosnian public-safe observation notes.",
    )

    notes_public_en = models.TextField(
        blank=True,
        help_text="English public-safe observation notes.",
    )

    notes_private = models.TextField(
        blank=True,
        help_text="Private internal notes. Never expose through public APIs later.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_observations",
        blank=True,
        null=True,
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_observations",
        blank=True,
        null=True,
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when this observation was verified by a human reviewer.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recorded_at", "code"]
        indexes = [
            models.Index(fields=["project", "observation_status"]),
            models.Index(fields=["project", "verification_status"]),
            models.Index(fields=["project", "recorded_at"]),
            models.Index(fields=["sensitivity_level", "visibility_level"]),
        ]
    def clean(self):
        """
        Validate impossible Observation status combinations.

        MVP purpose:
        - Protect the canonical Observation truth record from contradictory states.
        - Keep workflow services, admin edits, and future APIs aligned.
        - Catch impossible status pairs before they become scientific history.

        Architecture rule:
        - Observation is the scientific truth spine.
        - Observation status and verification status must tell the same lifecycle story.
        - Services still own workflow transitions; this model validation protects baseline truth.

        Left for later:
        - Add database-level constraints only after the workflow is stable.
        - Add public visibility/sensitivity validation once public-safe selectors exist.
        - Add project/location/evidence consistency validation in separate patches.
        """

        super().clean()

        errors = {}

        if self.observed_started_at and self.observed_ended_at:
            if self.observed_started_at > self.observed_ended_at:
                errors["observed_ended_at"] = (
                    "Observed end time cannot be earlier than observed start time."
                )

        if (
            self.observation_status == self.ObservationStatus.VERIFIED
            and self.verification_status != self.VerificationStatus.VERIFIED
        ):
            errors["verification_status"] = (
                "Verified observations must have verified verification status."
            )

        if (
            self.observation_status == self.ObservationStatus.PUBLISHED
            and self.verification_status != self.VerificationStatus.VERIFIED
        ):
            errors["verification_status"] = (
                "Published observations must remain scientifically verified."
            )

        if (
            self.observation_status == self.ObservationStatus.REJECTED
            and self.verification_status != self.VerificationStatus.REJECTED
        ):
            errors["verification_status"] = (
                "Rejected observations must have rejected verification status."
            )

        if (
            self.observation_status == self.ObservationStatus.DRAFT
            and self.verification_status == self.VerificationStatus.VERIFIED
        ):
            errors["verification_status"] = (
                "Draft observations cannot already be verified."
            )

        if (
            self.observation_status == self.ObservationStatus.SUBMITTED
            and self.verification_status == self.VerificationStatus.VERIFIED
        ):
            errors["verification_status"] = (
                "Submitted observations cannot already be verified."
            )

        if (
            self.observation_status == self.ObservationStatus.IN_REVIEW
            and self.verification_status == self.VerificationStatus.VERIFIED
        ):
            errors["verification_status"] = (
                "In-review observations cannot already be verified."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} - {self.get_observation_type_display()}"