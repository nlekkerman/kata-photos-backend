from django.contrib import admin

from monitoring.models import Camera, CameraDeployment, CameraMaintenanceRecord


class CameraDeploymentInline(admin.TabularInline):
    """
    Inline deployment history for a Camera.

    MVP purpose:
    - Show where a camera has been deployed over time.
    - Keep location history separate from the Camera hardware record.
    """

    model = CameraDeployment
    extra = 0
    fields = (
        "code",
        "project",
        "monitoring_point",
        "started_at",
        "ended_at",
        "status",
        "created_by",
    )
    autocomplete_fields = (
        "project",
        "monitoring_point",
        "created_by",
    )


class CameraMaintenanceRecordInline(admin.TabularInline):
    """
    Inline maintenance history for a Camera.

    MVP purpose:
    - Show inspections, battery changes, card changes, damage, and repairs from the Camera screen.
    - Preserve maintenance history instead of burying it in notes.
    """

    model = CameraMaintenanceRecord
    extra = 0
    fields = (
        "maintenance_type",
        "performed_at",
        "performed_by",
        "battery_changed",
        "memory_card_changed",
        "issue_detected",
    )
    autocomplete_fields = (
        "performed_by",
    )


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    """
    Django admin management for physical Camera hardware.

    MVP purpose:
    - Manually create and review trail cameras or future sensor-style camera devices.
    - Keep hardware identity separate from monitoring points and deployments.

    Important:
    Camera location history belongs to CameraDeployment, not Camera.
    """

    list_display = (
        "code",
        "name",
        "manufacturer",
        "model",
        "ownership_organization",
        "status",
    )
    list_filter = (
        "status",
        "ownership_organization",
        "manufacturer",
    )
    search_fields = (
        "code",
        "name",
        "manufacturer",
        "model",
        "serial_number",
        "ownership_organization__name",
    )
    autocomplete_fields = (
        "ownership_organization",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "uuid",
                    "code",
                    "name",
                    "ownership_organization",
                )
            },
        ),
        (
            "Hardware details",
            {
                "fields": (
                    "manufacturer",
                    "model",
                    "serial_number",
                    "purchase_date",
                    "warranty_until",
                )
            },
        ),
        (
            "Status and private notes",
            {
                "fields": (
                    "status",
                    "notes_private",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    inlines = [
        CameraDeploymentInline,
        CameraMaintenanceRecordInline,
    ]


@admin.register(CameraDeployment)
class CameraDeploymentAdmin(admin.ModelAdmin):
    """
    Django admin management for CameraDeployment records.

    MVP purpose:
    - Record camera placement at a monitoring point for a specific time range.
    - Preserve the chain Camera -> Deployment -> MonitoringPoint -> Project.

    Important:
    Overlap protection will be added later through a validator/service.
    """

    list_display = (
        "code",
        "camera",
        "project",
        "monitoring_point",
        "started_at",
        "ended_at",
        "status",
    )
    list_filter = (
        "status",
        "project",
        "monitoring_point",
        "camera",
    )
    search_fields = (
        "code",
        "camera__code",
        "camera__name",
        "project__name_bs",
        "monitoring_point__name_bs",
        "monitoring_point__code",
    )
    autocomplete_fields = (
        "project",
        "camera",
        "monitoring_point",
        "created_by",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Deployment identity",
            {
                "fields": (
                    "uuid",
                    "code",
                    "project",
                    "camera",
                    "monitoring_point",
                )
            },
        ),
        (
            "Time range and status",
            {
                "fields": (
                    "started_at",
                    "ended_at",
                    "status",
                )
            },
        ),
        (
            "Descriptions and private notes",
            {
                "fields": (
                    "deployment_notes",
                    "public_description_bs",
                    "public_description_en",
                )
            },
        ),
        (
            "Accountability",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(CameraMaintenanceRecord)
class CameraMaintenanceRecordAdmin(admin.ModelAdmin):
    """
    Django admin management for CameraMaintenanceRecord records.

    MVP purpose:
    - Track maintenance actions for cameras and deployments.
    - Preserve operational history that may later affect evidence quality.
    """

    list_display = (
        "camera",
        "maintenance_type",
        "performed_at",
        "performed_by",
        "battery_changed",
        "memory_card_changed",
    )
    list_filter = (
        "maintenance_type",
        "battery_changed",
        "memory_card_changed",
        "camera",
    )
    search_fields = (
        "camera__code",
        "camera__name",
        "deployment__code",
        "issue_detected",
        "notes",
    )
    autocomplete_fields = (
        "camera",
        "deployment",
        "performed_by",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Maintenance identity",
            {
                "fields": (
                    "uuid",
                    "camera",
                    "deployment",
                    "maintenance_type",
                )
            },
        ),
        (
            "Performed work",
            {
                "fields": (
                    "performed_at",
                    "performed_by",
                    "battery_changed",
                    "memory_card_changed",
                    "firmware_version",
                    "issue_detected",
                    "notes",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )