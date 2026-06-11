import uuid

from django.conf import settings
from django.db import models


class CameraMaintenanceRecord(models.Model):
    """
    Maintenance history for physical camera hardware.

    MVP purpose:
    - Preserve equipment maintenance events such as battery changes, inspections,
      memory card changes, damage reports, firmware updates, and repairs.
    - Keep maintenance history separate from Camera notes.

    Important architecture rule:
    Maintenance can affect evidence reliability later.
    Do not hide maintenance history in loose text fields.

    Left for later:
    - Maintenance workflow services.
    - Evidence quality impact rules.
    - Audit logging for damage/loss/sensitive maintenance notes.
    """

    class MaintenanceType(models.TextChoices):
        BATTERY_REPLACEMENT = "battery_replacement", "Battery replacement"
        MEMORY_CARD_REPLACEMENT = "memory_card_replacement", "Memory card replacement"
        LENS_CLEANING = "lens_cleaning", "Lens cleaning"
        FIRMWARE_UPDATE = "firmware_update", "Firmware update"
        PHYSICAL_REPAIR = "physical_repair", "Physical repair"
        INSPECTION = "inspection", "Inspection"
        RELOCATION_CHECK = "relocation_check", "Relocation check"
        DAMAGE_REPORT = "damage_report", "Damage report"
        OTHER = "other", "Other"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    camera = models.ForeignKey(
        "monitoring.Camera",
        on_delete=models.PROTECT,
        related_name="maintenance_records",
    )

    deployment = models.ForeignKey(
        "monitoring.CameraDeployment",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="maintenance_records",
    )

    maintenance_type = models.CharField(
        max_length=40,
        choices=MaintenanceType.choices,
        default=MaintenanceType.INSPECTION,
    )

    performed_at = models.DateTimeField()
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="performed_camera_maintenance_records",
    )

    notes = models.TextField(blank=True)

    battery_changed = models.BooleanField(default=False)
    memory_card_changed = models.BooleanField(default=False)

    firmware_version = models.CharField(max_length=80, blank=True)
    issue_detected = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Camera maintenance record"
        verbose_name_plural = "Camera maintenance records"
        ordering = ["-performed_at"]
        indexes = [
            models.Index(fields=["camera", "performed_at"]),
            models.Index(fields=["deployment", "performed_at"]),
            models.Index(fields=["maintenance_type"]),
            models.Index(fields=["performed_at"]),
        ]

    def __str__(self):
        return f"{self.camera} - {self.get_maintenance_type_display()} at {self.performed_at}"