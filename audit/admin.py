from django.contrib import admin

from .models import AuditRecord


@admin.register(AuditRecord)
class AuditRecordAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action_type",
        "severity",
        "target_object_type",
        "target_object_id",
        "actor",
        "actor_label",
        "organization_id",
        "project_id",
        "contains_sensitive_data",
        "contains_private_coordinates",
        "contains_restricted_fields",
    )

    list_filter = (
        "action_type",
        "severity",
        "visibility_level",
        "sensitivity_level",
        "contains_sensitive_data",
        "contains_private_coordinates",
        "contains_restricted_fields",
        "target_object_type",
        "created_at",
    )

    search_fields = (
        "uuid",
        "target_object_type",
        "target_object_id",
        "actor__username",
        "actor__email",
        "actor_label",
        "acting_membership_id",
        "organization_id",
        "project_id",
        "scope",
        "capability_used",
        "request_id",
        "reason",
        "note",
    )

    readonly_fields = (
        "uuid",
        "actor",
        "actor_label",
        "action_type",
        "target_object_type",
        "target_object_id",
        "acting_membership_id",
        "organization_id",
        "project_id",
        "scope",
        "capability_used",
        "visibility_level",
        "sensitivity_level",
        "severity",
        "contains_sensitive_data",
        "contains_private_coordinates",
        "contains_restricted_fields",
        "before_snapshot",
        "after_snapshot",
        "metadata",
        "request_id",
        "reason",
        "note",
        "created_at",
    )

    fieldsets = (
        (
            "Core Action",
            {
                "fields": (
                    "uuid",
                    "created_at",
                    "actor",
                    "actor_label",
                    "action_type",
                    "severity",
                )
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "target_object_type",
                    "target_object_id",
                )
            },
        ),
        (
            "Scope / Authorization Context",
            {
                "fields": (
                    "acting_membership_id",
                    "organization_id",
                    "project_id",
                    "scope",
                    "capability_used",
                    "visibility_level",
                    "sensitivity_level",
                )
            },
        ),
        (
            "Sensitive Data Flags",
            {
                "fields": (
                    "contains_sensitive_data",
                    "contains_private_coordinates",
                    "contains_restricted_fields",
                )
            },
        ),
        (
            "Snapshots",
            {
                "classes": ("collapse",),
                "fields": (
                    "before_snapshot",
                    "after_snapshot",
                ),
            },
        ),
        (
            "Metadata / Trace",
            {
                "classes": ("collapse",),
                "fields": (
                    "metadata",
                    "request_id",
                    "reason",
                    "note",
                ),
            },
        ),
    )

    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False