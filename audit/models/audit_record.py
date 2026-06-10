import uuid

from django.conf import settings
from django.db import models


class AuditRecord(models.Model):
    """
    Protected accountability log for Kata Wild.

    AuditRecord records important actions, sensitive reads, permission-affecting
    changes, scientific workflow decisions, and high-risk exports.

    Audit is NOT scientific truth.
    Observation, ObservationRevision, Evidence, Membership, RoleCapability,
    ProjectCollaboration, ResearchExport, and other domain models keep their own
    canonical truth. AuditRecord records that an action happened.
    """

    class ActionType(models.TextChoices):
        # Generic lifecycle
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        ARCHIVED = "archived", "Archived"
        DELETED = "deleted", "Deleted"

        # Status / workflow
        STATUS_CHANGED = "status_changed", "Status changed"
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        UNPUBLISHED = "unpublished", "Unpublished"
        REVISED = "revised", "Revised"

        # Access / RBAC
        ACCESS_GRANTED = "access_granted", "Access granted"
        ACCESS_REVOKED = "access_revoked", "Access revoked"
        ROLE_ASSIGNED = "role_assigned", "Role assigned"
        ROLE_REMOVED = "role_removed", "Role removed"
        CAPABILITY_ASSIGNED = "capability_assigned", "Capability assigned"
        CAPABILITY_REMOVED = "capability_removed", "Capability removed"
        PERMISSION_CHANGED = "permission_changed", "Permission changed"

        # Sensitive reads
        SENSITIVE_DATA_VIEWED = "sensitive_data_viewed", "Sensitive data viewed"
        PRIVATE_COORDINATES_VIEWED = (
            "private_coordinates_viewed",
            "Private coordinates viewed",
        )
        PRIVATE_GEOMETRY_VIEWED = "private_geometry_viewed", "Private geometry viewed"
        RESTRICTED_RECORD_VIEWED = (
            "restricted_record_viewed",
            "Restricted record viewed",
        )

        # Evidence / research / export
        EVIDENCE_LINKED = "evidence_linked", "Evidence linked"
        EVIDENCE_UNLINKED = "evidence_unlinked", "Evidence unlinked"
        EXPORT_GENERATED = "export_generated", "Export generated"
        EXPORT_DOWNLOADED = "export_downloaded", "Export downloaded"

        # AI / internal / system
        AI_SUGGESTION_REVIEWED = (
            "ai_suggestion_reviewed",
            "AI suggestion reviewed",
        )
        INTERNAL_WORKFLOW_RAN = "internal_workflow_ran", "Internal workflow ran"
        SYSTEM_CONFIGURATION_CHANGED = (
            "system_configuration_changed",
            "System configuration changed",
        )

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner"
        RESEARCH = "research", "Research"
        RESTRICTED = "restricted", "Restricted"
        UNKNOWN = "unknown", "Unknown"

    class SensitivityLevel(models.TextChoices):
        NONE = "none", "None"
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_records",
        help_text="User who performed the action. Null is allowed for system actions.",
    )

    actor_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Snapshot label of the actor at the time of action, for example username/email.",
    )

    action_type = models.CharField(
        max_length=80,
        choices=ActionType.choices,
        db_index=True,
    )

    target_object_type = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Canonical target type, for example Observation, Project, Taxon.",
    )

    target_object_id = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text="Target primary key, UUID, permanent code, or external identifier.",
    )

    # These are intentionally loose at MVP stage because organizations, projects,
    # and memberships may not exist at the moment this app is created.
    # Later, services can pass real IDs/codes without causing circular imports.
    acting_membership_id = models.CharField(
        max_length=120,
        blank=True,
        help_text="Membership context used for the action, when available.",
    )

    organization_id = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text="Acting organization or organization scope, when available.",
    )

    project_id = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text="Project scope, when available.",
    )

    scope = models.CharField(
        max_length=160,
        blank=True,
        help_text="Optional human-readable scope, for example project:PRJ-000001.",
    )

    capability_used = models.CharField(
        max_length=120,
        blank=True,
        help_text="Capability used to authorize the action, when applicable.",
    )

    visibility_level = models.CharField(
        max_length=40,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.UNKNOWN,
    )

    sensitivity_level = models.CharField(
        max_length=40,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.UNKNOWN,
    )

    severity = models.CharField(
        max_length=40,
        choices=Severity.choices,
        default=Severity.INFO,
    )

    contains_sensitive_data = models.BooleanField(
        default=False,
        help_text="True when the action involved sensitive/protected data.",
    )

    contains_private_coordinates = models.BooleanField(
        default=False,
        help_text="True when exact/private coordinates were viewed or exported.",
    )

    contains_restricted_fields = models.BooleanField(
        default=False,
        help_text="True when restricted fields were viewed, changed, or exported.",
    )

    before_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional compact snapshot before the action.",
    )

    after_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional compact snapshot after the action.",
    )

    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional structured context, such as export privacy mode or request source.",
    )

    request_id = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text="Optional request/correlation ID for tracing one request across logs.",
    )

    reason = models.TextField(
        blank=True,
        help_text="Reason supplied by actor, reviewer, admin, or workflow.",
    )

    note = models.TextField(
        blank=True,
        help_text="Internal audit note.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Audit record"
        verbose_name_plural = "Audit records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["target_object_type", "target_object_id"]),
            models.Index(fields=["organization_id", "created_at"]),
            models.Index(fields=["project_id", "created_at"]),
            models.Index(fields=["request_id", "created_at"]),
            models.Index(fields=["contains_sensitive_data", "created_at"]),
            models.Index(fields=["contains_private_coordinates", "created_at"]),
            models.Index(fields=["contains_restricted_fields", "created_at"]),
        ]

    def __str__(self):
        target = f"{self.target_object_type}:{self.target_object_id}".strip(":")
        return f"{self.action_type} -> {target}"