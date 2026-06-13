# observations/services/observation_audit_service.py

from typing import Any, Optional

from audit.models import AuditRecord
from audit.services.audit_record_create_service import create_audit_record
from organizations.models.organization import Organization
from observations.models.observation import Observation
from observations.models.observation_revision import ObservationRevision


def _object_identifier(obj: Any) -> str:
    """
    Return a stable readable identifier for audit scope fields.

    MVP purpose:
    - Prefer permanent/code-style fields when they exist.
    - Fall back safely to pk without requiring every model to share one field name.
    """

    if obj is None:
        return ""

    for field_name in ("code", "slug", "uuid", "permanent_code", "observation_code"):
        value = getattr(obj, field_name, None)
        if value:
            return str(value)

    pk = getattr(obj, "pk", None)
    return str(pk) if pk else ""


def _audit_visibility_level(value: str) -> str:
    """
    Map Observation visibility into AuditRecord visibility safely.
    """

    valid_values = {choice[0] for choice in AuditRecord.VisibilityLevel.choices}

    if value in valid_values:
        return value

    return AuditRecord.VisibilityLevel.UNKNOWN


def _audit_sensitivity_level(value: str) -> str:
    """
    Map Observation sensitivity into AuditRecord sensitivity safely.

    Observation may use scientific/conservation wording while AuditRecord uses
    audit severity-style wording. Keep this explicit instead of guessing silently.
    """

    mapping = {
        "none": AuditRecord.SensitivityLevel.NONE,
        "normal": AuditRecord.SensitivityLevel.LOW,
        "low": AuditRecord.SensitivityLevel.LOW,
        "sensitive": AuditRecord.SensitivityLevel.MODERATE,
        "moderate": AuditRecord.SensitivityLevel.MODERATE,
        "high": AuditRecord.SensitivityLevel.HIGH,
        "highly_sensitive": AuditRecord.SensitivityLevel.HIGH,
        "critical": AuditRecord.SensitivityLevel.CRITICAL,
    }

    return mapping.get(value, AuditRecord.SensitivityLevel.UNKNOWN)


def _observation_status_snapshot(*, observation: Observation) -> dict[str, Any]:
    """
    Compact audit snapshot for observation workflow state.

    Keep audit snapshots small. Audit is accountability, not a full duplicate
    of canonical Observation truth.
    """

    return {
        "observation_id": observation.pk,
        "observation_code": _object_identifier(observation),
        "observation_status": observation.observation_status,
        "verification_status": observation.verification_status,
        "visibility_level": getattr(observation, "visibility_level", ""),
        "sensitivity_level": getattr(observation, "sensitivity_level", ""),
        "verified_by_id": getattr(observation, "verified_by_id", None),
        "verified_at": (
            observation.verified_at.isoformat()
            if getattr(observation, "verified_at", None)
            else None
        ),
    }


def create_observation_workflow_audit_record(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization],
    action_type: str,
    capability_used: str,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    revision: ObservationRevision,
    reason: str = "",
    note: str = "",
):
    """
    Create audit record for protected Observation workflow actions.

    MVP purpose:
    - Verification, publication, and unpublication are scientific workflow actions.
    - Audit records who performed the action, under which org/project context,
      and what state changed.
    """

    project = getattr(observation, "project", None)
    sensitivity_value = getattr(observation, "sensitivity_level", "")
    visibility_value = getattr(observation, "visibility_level", "")

    audit_sensitivity = _audit_sensitivity_level(sensitivity_value)

    contains_sensitive_data = audit_sensitivity in {
        AuditRecord.SensitivityLevel.MODERATE,
        AuditRecord.SensitivityLevel.HIGH,
        AuditRecord.SensitivityLevel.CRITICAL,
    }

    contains_restricted_fields = (
        visibility_value == "restricted"
        or audit_sensitivity
        in {
            AuditRecord.SensitivityLevel.HIGH,
            AuditRecord.SensitivityLevel.CRITICAL,
        }
    )

    return create_audit_record(
        actor=user,
        action_type=action_type,
        target_object_type="Observation",
        target_object_id=_object_identifier(observation),
        acting_membership_id="",
        organization_id=_object_identifier(organization),
        project_id=_object_identifier(project),
        scope=f"project:{_object_identifier(project)}" if project else "",
        capability_used=capability_used,
        visibility_level=_audit_visibility_level(visibility_value),
        sensitivity_level=audit_sensitivity,
        severity=(
            AuditRecord.Severity.HIGH
            if contains_sensitive_data or contains_restricted_fields
            else AuditRecord.Severity.INFO
        ),
        contains_sensitive_data=contains_sensitive_data,
        contains_private_coordinates=False,
        contains_restricted_fields=contains_restricted_fields,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata={
            "revision_id": revision.pk,
            "revision_type": revision.revision_type,
        },
        reason=reason,
        note=note,
    )


__all__ = [
    "_observation_status_snapshot",
    "create_observation_workflow_audit_record",
]