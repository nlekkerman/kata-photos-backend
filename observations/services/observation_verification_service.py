from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from organizations.models.organization import Organization
from observations.models.observation import Observation
from observations.models.observation_review import ObservationReview
from observations.models.observation_revision import ObservationRevision
from observations.policies.observation_verification_policy import (
    can_verify_observation,
)


class ObservationVerificationDenied(Exception):
    """
    Raised when a user is not allowed to verify an observation.

    MVP purpose:
    - Keep service-level permission failures explicit.
    - Avoid silently changing canonical scientific truth.
    """


@dataclass(frozen=True)
class ObservationVerificationServiceResult:
    """
    Result returned after successful observation verification.

    MVP purpose:
    - Return the updated observation plus created review/revision records.
    - Keep future views/APIs from guessing what happened.
    """

    observation: Observation
    review: ObservationReview
    revision: ObservationRevision


@transaction.atomic
def verify_observation(
    *,
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
    review_notes: str = "",
    revision_reason: str = "",
) -> ObservationVerificationServiceResult:
    """
    Verify an observation as human-reviewed scientific truth.

    MVP workflow:
    - Check observation verification policy.
    - Update the canonical Observation.
    - Create an ObservationReview record.
    - Create an ObservationRevision record.

    Important architecture rule:
    Services change truth.
    Policies decide access.
    This service must not bypass policy.

    Left for later:
    - Dedicated validator for allowed status transitions.
    - AuditRecord creation.
    - Realtime event after transaction commit.
    - More detailed before/after snapshots.
    """

    policy_result = can_verify_observation(
        user=user,
        observation=observation,
        organization=organization,
    )

    if not policy_result.allowed:
        raise ObservationVerificationDenied(policy_result.reason)

    verified_at = timezone.now()

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status

    observation.observation_status = Observation.ObservationStatus.VERIFIED
    observation.verification_status = Observation.VerificationStatus.VERIFIED
    observation.verified_by = user
    observation.verified_at = verified_at

    observation.save(
        update_fields=[
            "observation_status",
            "verification_status",
            "verified_by",
            "verified_at",
            "updated_at",
        ]
    )

    review = ObservationReview.objects.create(
        observation=observation,
        reviewed_by=user,
        review_status=ObservationReview.ReviewStatus.VERIFIED,
        review_notes=review_notes,
        reviewed_at=verified_at,
    )

    revision = ObservationRevision.objects.create(
        observation=observation,
        revision_type=ObservationRevision.RevisionType.VERIFICATION_CHANGED,
        changed_by=user,
        reason=revision_reason or "Observation verified through MVP verification service.",
        previous_observation_status=previous_observation_status,
        new_observation_status=observation.observation_status,
        previous_verification_status=previous_verification_status,
        new_verification_status=observation.verification_status,
        notes=review_notes,
    )

    return ObservationVerificationServiceResult(
        observation=observation,
        review=review,
        revision=revision,
    )