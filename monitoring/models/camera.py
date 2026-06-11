import uuid

from django.db import models


class Camera(models.Model):
    """
    Physical camera hardware used by Kata Wild.

    MVP purpose:
    - Store the identity and lifecycle of a real camera device.
    - Keep camera hardware separate from location.
    - Prepare future camera deployment, maintenance, and observation workflows.

    Important architecture rule:
    A Camera can move.
    A Camera is not a MonitoringPoint.
    CameraDeployment preserves where and when a camera was placed.

    Left for later:
    - Camera ownership transfer workflow.
    - Device health/realtime status.
    - Provider/device integration adapters.
    - Audit logging for retirement/loss/sensitive notes.
    """

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        PURCHASED = "purchased", "Purchased"
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"
        BROKEN = "broken", "Broken"
        LOST = "lost", "Lost"
        RETIRED = "retired", "Retired"
        ARCHIVED = "archived", "Archived"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)

    name = models.CharField(max_length=180)
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)

    ownership_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="owned_cameras",
    )

    purchase_date = models.DateField(blank=True, null=True)
    warranty_until = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNED,
    )

    # Private operational notes may contain sensitive deployment or equipment details.
    # Public APIs must never expose this directly.
    notes_private = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Camera"
        verbose_name_plural = "Cameras"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["ownership_organization", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["serial_number"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"