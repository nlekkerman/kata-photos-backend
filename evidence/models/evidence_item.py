import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EvidenceItem(models.Model):
    """
    Canonical evidence record.

    EvidenceItem stores the existence and scientific context of a piece of
    evidence, such as a trail-camera video, photo, audio clip, manual field
    note, or future sensor/drone record.

    MVP scope:
    - Store evidence metadata.
    - Link evidence to Project, optional MonitoringPoint, and optional CameraDeployment.
    - Keep evidence separate from verified Observation truth.

    Left for later:
    - Evidence verification workflow.
    - Observation creation from verified evidence.
    - Sensitivity/public redaction policy.
    - Audit logging for protected evidence access.
    """

    class EvidenceType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        FIELD_NOTE = "field_note", "Field note"
        SENSOR_RECORD = "sensor_record", "Sensor record"
        DRONE_MEDIA = "drone_media", "Drone media"
        OTHER = "other", "Other"

    class SourceType(models.TextChoices):
        TRAIL_CAMERA = "trail_camera", "Trail camera"
        MANUAL_UPLOAD = "manual_upload", "Manual upload"
        FIELD_OBSERVER = "field_observer", "Field observer"
        DRONE = "drone", "Drone"
        SENSOR = "sensor", "Sensor"
        ARCHIVE = "archive", "Archive"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        REVIEW_NEEDED = "review_needed", "Review needed"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class SensitivityLevel(models.TextChoices):
        NORMAL = "normal", "Normal"
        SENSITIVE = "sensitive", "Sensitive"
        RESTRICTED = "restricted", "Restricted"

    class VisibilityLevel(models.TextChoices):
        PRIVATE = "private", "Private"
        INTERNAL = "internal", "Internal"
        RESEARCH = "research", "Research"
        PUBLIC_SAFE = "public_safe", "Public safe"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(
        max_length=80,
        unique=True,
        help_text="Stable backend evidence code, for example EVD-PLJ-001.",
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="evidence_items",
        help_text="Project that owns this evidence record.",
    )

    monitoring_point = models.ForeignKey(
        "locations.MonitoringPoint",
        on_delete=models.PROTECT,
        related_name="evidence_items",
        blank=True,
        null=True,
        help_text="Optional permanent monitoring point where this evidence was captured.",
    )

    camera_deployment = models.ForeignKey(
        "monitoring.CameraDeployment",
        on_delete=models.PROTECT,
        related_name="evidence_items",
        blank=True,
        null=True,
        help_text="Optional deployment active when this evidence was captured.",
    )

    evidence_type = models.CharField(
        max_length=40,
        choices=EvidenceType.choices,
        default=EvidenceType.VIDEO,
    )

    source_type = models.CharField(
        max_length=40,
        choices=SourceType.choices,
        default=SourceType.TRAIL_CAMERA,
    )

    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )

    sensitivity_level = models.CharField(
        max_length=40,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.NORMAL,
    )

    visibility_level = models.CharField(
        max_length=40,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.PRIVATE,
    )

    capture_started_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional start time when the evidence capture began.",
    )

    capture_ended_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional end time when the evidence capture ended.",
    )

    recorded_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Main recorded timestamp if only one timestamp is known.",
    )

    title_bs = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)

    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    notes_private = models.TextField(
        blank=True,
        help_text="Private internal notes. Never expose this in public APIs.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_evidence_items",
        blank=True,
        null=True,
        help_text="User who created/submitted this evidence record.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recorded_at", "-capture_started_at", "-created_at"]
        verbose_name = "Evidence item"
        verbose_name_plural = "Evidence items"
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["evidence_type", "status"]),
            models.Index(fields=["sensitivity_level", "visibility_level"]),
            models.Index(fields=["recorded_at"]),
            models.Index(fields=["capture_started_at"]),
        ]
        
    def clean(self):
        """
        Validate EvidenceItem project and capture-context consistency.

        MVP purpose:
        - Keep evidence tied to one coherent project context.
        - Prevent evidence from referencing monitoring points or deployments from another project.
        - Protect downstream Observation creation from corrupted evidence context.

        Architecture rule:
        - Evidence supports Observation truth but does not replace Observation truth.
        - EvidenceItem project, monitoring point, and camera deployment must describe
          the same scientific context.
        - CameraDeployment is time-bound placement context for camera-based evidence.

        Left for later:
        - Evidence create/update service with audit logging.
        - Public-safe evidence selectors and redaction policy.
        - Automatic recorded_at derivation from capture_started_at if desired.
        """

        super().clean()

        errors = {}

        if self.capture_started_at and self.capture_ended_at:
            if self.capture_started_at > self.capture_ended_at:
                errors["capture_ended_at"] = (
                    "Evidence capture end time cannot be earlier than capture start time."
                )

        if self.monitoring_point_id and self.project_id:
            if self.monitoring_point.project_id != self.project_id:
                errors["monitoring_point"] = (
                    "Evidence monitoring point must belong to the same project."
                )

        if self.camera_deployment_id and self.project_id:
            if self.camera_deployment.project_id != self.project_id:
                errors["camera_deployment"] = (
                    "Evidence camera deployment must belong to the same project."
                )

        if self.monitoring_point_id and self.camera_deployment_id:
            if self.camera_deployment.monitoring_point_id != self.monitoring_point_id:
                errors["camera_deployment"] = (
                    "Evidence camera deployment must match the selected monitoring point."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} - {self.title_bs}"