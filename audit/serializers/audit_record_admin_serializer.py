from rest_framework import serializers

from audit.models import AuditRecord


class AuditRecordAdminListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditRecord
        fields = (
            "uuid",
            "created_at",
            "actor",
            "actor_label",
            "action_type",
            "severity",
            "target_object_type",
            "target_object_id",
            "organization_id",
            "project_id",
            "scope",
            "capability_used",
            "visibility_level",
            "sensitivity_level",
            "contains_sensitive_data",
            "contains_private_coordinates",
            "contains_restricted_fields",
            "request_id",
        )
        read_only_fields = fields


class AuditRecordAdminDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditRecord
        fields = (
            "id",
            "uuid",
            "created_at",
            "actor",
            "actor_label",
            "action_type",
            "severity",
            "target_object_type",
            "target_object_id",
            "acting_membership_id",
            "organization_id",
            "project_id",
            "scope",
            "capability_used",
            "visibility_level",
            "sensitivity_level",
            "contains_sensitive_data",
            "contains_private_coordinates",
            "contains_restricted_fields",
            "before_snapshot",
            "after_snapshot",
            "metadata",
            "request_id",
            "reason",
            "note",
        )
        read_only_fields = fields