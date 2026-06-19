import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CameraDeployment(models.Model):
    """
    Time-bound placement of a Camera at a MonitoringPoint.

    MVP purpose:
    - Record where a camera was deployed and during what time range.
    - Preserve camera movement history.
    - Prepare future camera-based observations and evidence linking.

    Important architecture rule:
    CameraDeployment is the scientific context for camera-based records.
    Do not store camera location by editing Camera directly.
    Do not move MonitoringPoint. Create new deployments when cameras move.

    Left for later:
    - Overlap validation to prevent one camera from having two active deployments.
    - Deployment start/end services.
    - Private deployment note access policy.
    - Audit logging for deployment changes.
    """

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"
        RETIRED = "retired", "Retired"
        ARCHIVED = "archived", "Archived"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="camera_deployments",
    )
    camera = models.ForeignKey(
        "monitoring.Camera",
        on_delete=models.PROTECT,
        related_name="deployments",
    )
    monitoring_point = models.ForeignKey(
        "locations.MonitoringPoint",
        on_delete=models.PROTECT,
        related_name="camera_deployments",
    )

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNED,
    )

    # Private deployment notes may include exact placement hints, access routes,
    # or conservation-sensitive context. Public APIs must not expose this directly.
    deployment_notes = models.TextField(blank=True)

    public_description_bs = models.TextField(blank=True)
    public_description_en = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_camera_deployments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Camera deployment"
        verbose_name_plural = "Camera deployments"
        ordering = ["-started_at", "code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["camera", "status"]),
            models.Index(fields=["monitoring_point", "status"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["ended_at"]),
        ]
        
    def clean(self):
        """
        Validate camera deployment timing and project context.

        MVP purpose:
        - Prevent one deployment from having impossible dates.
        - Keep deployment project aligned with the selected monitoring point.
        - Prevent one camera from having overlapping active placement windows.

        Architecture rule:
        - CameraDeployment is the time-bound placement context for camera evidence.
        - Camera location history belongs here, not directly on Camera.
        - A camera cannot be physically active in two overlapping deployments.

        Left for later:
        - Dedicated deployment start/end services.
        - Audit logging for deployment changes.
        - More advanced validation for paused/retired/archive workflows.
        """

        super().clean()

        errors = {}

        if self.started_at and self.ended_at:
            if self.started_at > self.ended_at:
                errors["ended_at"] = (
                    "Deployment end time cannot be earlier than deployment start time."
                )

        if self.monitoring_point_id and self.project_id:
            if self.monitoring_point.project_id != self.project_id:
                errors["monitoring_point"] = (
                    "Deployment monitoring point must belong to the same project."
                )

        overlapping_statuses = {
            self.Status.PLANNED,
            self.Status.ACTIVE,
            self.Status.PAUSED,
        }

        if (
            self.camera_id
            and self.started_at
            and self.status in overlapping_statuses
        ):
            overlapping_deployments = CameraDeployment.objects.filter(
                camera_id=self.camera_id,
                status__in=overlapping_statuses,
            ).exclude(pk=self.pk)

            if self.ended_at:
                overlapping_deployments = overlapping_deployments.filter(
                    started_at__lte=self.ended_at,
                )

            overlapping_deployments = overlapping_deployments.filter(
                models.Q(ended_at__isnull=True)
                | models.Q(ended_at__gte=self.started_at)
            )

            if overlapping_deployments.exists():
                errors["camera"] = (
                    "Camera already has an overlapping planned, active, or paused deployment."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} - {self.camera} at {self.monitoring_point}"