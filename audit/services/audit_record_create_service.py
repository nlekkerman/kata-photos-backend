from typing import Any

from django.contrib.auth import get_user_model

from audit.models import AuditRecord


UserModel = get_user_model()


def build_actor_label(*, actor: UserModel | None) -> str:
    """
    Store a stable actor label so audit remains readable even if the user is
    later deleted and the FK becomes null.
    """

    if actor is None:
        return "System"

    email = getattr(actor, "email", "") or ""
    username = getattr(actor, "username", "") or ""

    if email and username:
        return f"{username} <{email}>"

    return email or username or f"User #{actor.pk}"


def create_audit_record(
    *,
    actor: UserModel | None,
    action_type: str,
    target_object_type: str,
    target_object_id: str = "",
    acting_membership_id: str = "",
    organization_id: str = "",
    project_id: str = "",
    scope: str = "",
    capability_used: str = "",
    visibility_level: str = AuditRecord.VisibilityLevel.UNKNOWN,
    sensitivity_level: str = AuditRecord.SensitivityLevel.UNKNOWN,
    severity: str = AuditRecord.Severity.INFO,
    contains_sensitive_data: bool = False,
    contains_private_coordinates: bool = False,
    contains_restricted_fields: bool = False,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str = "",
    reason: str = "",
    note: str = "",
) -> AuditRecord:
    """
    Create an immutable audit record.

    Other apps should call this service instead of creating AuditRecord directly.
    This keeps audit creation consistent and ready for RBAC, exports, sensitive
    reads, and scientific workflows.
    """

    return AuditRecord.objects.create(
        actor=actor,
        actor_label=build_actor_label(actor=actor),
        action_type=action_type,
        target_object_type=target_object_type,
        target_object_id=str(target_object_id) if target_object_id else "",
        acting_membership_id=str(acting_membership_id) if acting_membership_id else "",
        organization_id=str(organization_id) if organization_id else "",
        project_id=str(project_id) if project_id else "",
        scope=scope,
        capability_used=capability_used,
        visibility_level=visibility_level,
        sensitivity_level=sensitivity_level,
        severity=severity,
        contains_sensitive_data=contains_sensitive_data,
        contains_private_coordinates=contains_private_coordinates,
        contains_restricted_fields=contains_restricted_fields,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata=metadata,
        request_id=request_id,
        reason=reason,
        note=note,
    )