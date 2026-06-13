from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from audit.models import AuditRecord
from organizations.models.organization import Organization
from observations.models.observation import Observation
from observations.models.observation_review import ObservationReview
from observations.models.observation_revision import ObservationRevision
from observations.policies.observation_verification_policy import (
    can_reopen_observation,
)
from observations.services.observation_audit_service import (
    _observation_status_snapshot,
    create_observation_workflow_audit_record,
)
from observations.validators.observation_transition_validator import (
    require_observation_transition,
)

class ObservationReopenDenied(Exception):
    """
    Raised when a user is not allowed to reopen a rejected observation.

    MVP purpose:
    - Keep rejected observation recovery explicit.
    - Avoid weakening normal verification workflow.
    """


@dataclass(frozen=True)
class ObservationReopenServiceResult:
    """
    Result returned after successful observation reopen.

    MVP purpose:
    - Return the updated observation plus created review/revision records.
    - Keep future views/APIs from guessing what happened.
    """

    observation: Observation
    review: ObservationReview
    revision: ObservationRevision


@transaction.atomic
def reopen_observation(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
    review_notes: str = "",
    revision_reason: str = "",
) -> ObservationReopenServiceResult:
    """
    Reopen a rejected observation for review.

    MVP workflow:
    - Check observation reopen policy.
    - Capture compact before snapshot for audit.
    - Move Observation from rejected back into review workflow.
    - Create an ObservationReview record.
    - Create an ObservationRevision record.
    - Create an AuditRecord for accountability.

    Important architecture rule:
    Reopen does not verify truth.
    Reopen only makes a rejected observation reviewable again.
    Verification must still happen later through verify_observation().
    """

    policy_result = can_reopen_observation(
        user=user,
        observation=observation,
        organization=organization,
    )

    if not policy_result.allowed:
        raise ObservationReopenDenied(policy_result.reason)

    require_observation_transition(
        observation=observation,
        new_observation_status=Observation.ObservationStatus.IN_REVIEW,
        new_verification_status=Observation.VerificationStatus.REVIEW_NEEDED,
    )

    reopened_at = timezone.now()

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status
    before_snapshot = _observation_status_snapshot(observation=observation)

    observation.observation_status = Observation.ObservationStatus.IN_REVIEW
    observation.verification_status = Observation.VerificationStatus.REVIEW_NEEDED

    observation.save(
        update_fields=[
            "observation_status",
            "verification_status",
            "updated_at",
        ]
    )

    review = ObservationReview.objects.create(
        observation=observation,
        reviewed_by=user,
        review_status=ObservationReview.ReviewStatus.REVIEW_NEEDED,
        review_notes=review_notes,
        reviewed_at=reopened_at,
    )

    revision = ObservationRevision.objects.create(
        observation=observation,
        revision_type=ObservationRevision.RevisionType.STATUS_CHANGED,
        changed_by=user,
        reason=revision_reason or "Observation reopened through MVP reopen service.",
        previous_observation_status=previous_observation_status,
        new_observation_status=observation.observation_status,
        previous_verification_status=previous_verification_status,
        new_verification_status=observation.verification_status,
        notes=review_notes,
    )

    after_snapshot = _observation_status_snapshot(observation=observation)

    create_observation_workflow_audit_record(
        user=user,
        observation=observation,
        organization=organization,
        action_type=AuditRecord.ActionType.REVISED,
        capability_used="revise_observations",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        revision=revision,
        reason=revision_reason,
        note=review_notes,
    )

    return ObservationReopenServiceResult(
        observation=observation,
        review=review,
        revision=revision,
    )