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
    can_reject_observation,
)
from observations.services.observation_audit_service import (
    _observation_status_snapshot,
    create_observation_workflow_audit_record,
)
from observations.validators.observation_transition_validator import (
    require_observation_transition,
)

class ObservationRejectionDenied(Exception):
    """
    Raised when a user is not allowed to reject an observation.

    MVP purpose:
    - Keep rejection permission failures explicit.
    - Avoid silently changing canonical scientific truth.
    """


@dataclass(frozen=True)
class ObservationRejectionServiceResult:
    """
    Result returned after successful observation rejection.

    MVP purpose:
    - Return the updated observation plus created review/revision records.
    - Keep future views/APIs from guessing what happened.
    """

    observation: Observation
    review: ObservationReview
    revision: ObservationRevision


@transaction.atomic
def reject_observation(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
    review_notes: str = "",
    revision_reason: str = "",
) -> ObservationRejectionServiceResult:
    """
    Reject an observation after human review.

    MVP workflow:
    - Check observation rejection policy.
    - Capture compact before snapshot for audit.
    - Update the canonical Observation to rejected.
    - Create an ObservationReview record.
    - Create an ObservationRevision record.
    - Create an AuditRecord for accountability.

    Important architecture rule:
    Services change truth.
    Policies decide access.
    Audit records that a protected workflow action happened.
    Rejected observations are preserved, not deleted.

    Left for later:
    - Dedicated validator for allowed status transitions.
    - Rejection reason categories.
    - Reopen/revise rejected observation workflow.
    - Realtime event after transaction commit.
    """

    policy_result = can_reject_observation(
        user=user,
        observation=observation,
        organization=organization,
    )

    if not policy_result.allowed:
        raise ObservationRejectionDenied(policy_result.reason)

    require_observation_transition(
        observation=observation,
        new_observation_status=Observation.ObservationStatus.REJECTED,
        new_verification_status=Observation.VerificationStatus.REJECTED,
    )

    rejected_at = timezone.now()

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status
    before_snapshot = _observation_status_snapshot(observation=observation)

    observation.observation_status = Observation.ObservationStatus.REJECTED
    observation.verification_status = Observation.VerificationStatus.REJECTED

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
        review_status=ObservationReview.ReviewStatus.REJECTED,
        review_notes=review_notes,
        reviewed_at=rejected_at,
    )

    revision = ObservationRevision.objects.create(
        observation=observation,
        revision_type=ObservationRevision.RevisionType.VERIFICATION_CHANGED,
        changed_by=user,
        reason=revision_reason or "Observation rejected through MVP rejection service.",
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
        action_type=AuditRecord.ActionType.REJECTED,
        capability_used="reject_observations",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        revision=revision,
        reason=revision_reason,
        note=review_notes,
    )

    return ObservationRejectionServiceResult(
        observation=observation,
        review=review,
        revision=revision,
    )