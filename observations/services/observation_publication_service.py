from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from audit.models import AuditRecord
from organizations.models.organization import Organization
from observations.models.observation import Observation
from observations.models.observation_revision import ObservationRevision
from observations.policies.observation_publication_policy import (
    can_publish_observation,
    can_unpublish_observation,
)
from observations.services.observation_audit_service import (
    _observation_status_snapshot,
    create_observation_workflow_audit_record,
)
from observations.validators.observation_transition_validator import (
    require_observation_transition,
)


class ObservationPublicationDenied(Exception):
    """
    Raised when a user is not allowed to publish or unpublish an observation.

    MVP purpose:
    - Keep publication permission failures explicit.
    - Avoid silently changing canonical scientific truth.
    """


@dataclass(frozen=True)
class ObservationPublicationServiceResult:
    """
    Result returned after successful observation publication/unpublication.

    MVP purpose:
    - Return the updated observation plus created revision record.
    - Keep future views/APIs from guessing what happened.
    """

    observation: Observation
    revision: ObservationRevision


@transaction.atomic
def publish_observation(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
    revision_reason: str = "",
    notes: str = "",
) -> ObservationPublicationServiceResult:
    """
    Publish a verified observation.

    MVP workflow:
    - Check observation publication policy.
    - Capture compact before snapshot for audit.
    - Update the canonical Observation status to published.
    - Create an ObservationRevision record.
    - Create an AuditRecord for accountability.

    Important architecture rule:
    Services change truth.
    Policies decide access.
    Audit records that a protected workflow action happened.
    This service must not bypass policy.

    Left for later:
    - Dedicated publication validator.
    - Public-safe selector validation.
    - Coordinate/sensitivity redaction checks.
    - Realtime event after transaction commit.
    """

    policy_result = can_publish_observation(
        user=user,
        observation=observation,
        organization=organization,
    )

    if not policy_result.allowed:
        raise ObservationPublicationDenied(policy_result.reason)

    require_observation_transition(
        observation=observation,
        new_observation_status=Observation.ObservationStatus.PUBLISHED,
        new_verification_status=Observation.VerificationStatus.VERIFIED,
    )

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status
    before_snapshot = _observation_status_snapshot(observation=observation)

    # Keep the database write aligned with the validated transition target.
    # Publication changes workflow status, but the observation remains
    # scientifically verified.
    observation.observation_status = Observation.ObservationStatus.PUBLISHED
    observation.verification_status = Observation.VerificationStatus.VERIFIED

    observation.save(
        update_fields=[
            "observation_status",
            "verification_status",
            "updated_at",
        ]
    )

    revision = ObservationRevision.objects.create(
        observation=observation,
        revision_type=ObservationRevision.RevisionType.STATUS_CHANGED,
        changed_by=user,
        reason=revision_reason or "Observation published through MVP publication service.",
        previous_observation_status=previous_observation_status,
        new_observation_status=observation.observation_status,
        previous_verification_status=previous_verification_status,
        new_verification_status=observation.verification_status,
        previous_visibility_level=observation.visibility_level,
        new_visibility_level=observation.visibility_level,
        previous_sensitivity_level=observation.sensitivity_level,
        new_sensitivity_level=observation.sensitivity_level,
        notes=notes,
    )

    after_snapshot = _observation_status_snapshot(observation=observation)

    create_observation_workflow_audit_record(
        user=user,
        observation=observation,
        organization=organization,
        action_type=AuditRecord.ActionType.PUBLISHED,
        capability_used="publish_observations",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        revision=revision,
        reason=revision_reason,
        note=notes,
    )

    return ObservationPublicationServiceResult(
        observation=observation,
        revision=revision,
    )


@transaction.atomic
def unpublish_observation(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
    revision_reason: str = "",
    notes: str = "",
) -> ObservationPublicationServiceResult:
    """
    Unpublish a published observation by returning it to verified status.

    MVP workflow:
    - Check observation unpublication policy.
    - Capture compact before snapshot for audit.
    - Update the canonical Observation status from published back to verified.
    - Create an ObservationRevision record.
    - Create an AuditRecord for accountability.

    Important:
    Unpublishing does not make the observation scientifically unverified.
    It only removes the published workflow state.
    """

    policy_result = can_unpublish_observation(
        user=user,
        observation=observation,
        organization=organization,
    )

    if not policy_result.allowed:
        raise ObservationPublicationDenied(policy_result.reason)

    require_observation_transition(
        observation=observation,
        new_observation_status=Observation.ObservationStatus.VERIFIED,
        new_verification_status=Observation.VerificationStatus.VERIFIED,
    )

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status
    before_snapshot = _observation_status_snapshot(observation=observation)

    # Keep the database write aligned with the validated transition target.
    # Unpublishing removes published workflow state, but it does not make
    # the observation scientifically unverified.
    observation.observation_status = Observation.ObservationStatus.VERIFIED
    observation.verification_status = Observation.VerificationStatus.VERIFIED

    observation.save(
        update_fields=[
            "observation_status",
            "verification_status",
            "updated_at",
        ]
    )

    revision = ObservationRevision.objects.create(
        observation=observation,
        revision_type=ObservationRevision.RevisionType.STATUS_CHANGED,
        changed_by=user,
        reason=revision_reason or "Observation unpublished through MVP publication service.",
        previous_observation_status=previous_observation_status,
        new_observation_status=observation.observation_status,
        previous_verification_status=previous_verification_status,
        new_verification_status=observation.verification_status,
        previous_visibility_level=observation.visibility_level,
        new_visibility_level=observation.visibility_level,
        previous_sensitivity_level=observation.sensitivity_level,
        new_sensitivity_level=observation.sensitivity_level,
        notes=notes,
    )

    after_snapshot = _observation_status_snapshot(observation=observation)

    create_observation_workflow_audit_record(
        user=user,
        observation=observation,
        organization=organization,
        action_type=AuditRecord.ActionType.UNPUBLISHED,
        capability_used="unpublish_observations",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        revision=revision,
        reason=revision_reason,
        note=notes,
    )

    return ObservationPublicationServiceResult(
        observation=observation,
        revision=revision,
    )