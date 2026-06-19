from dataclasses import dataclass
from typing import Optional

from organizations.models.organization import Organization

from access.services.capability_check_service import check_user_capability
from access.services.project_scope_service import organization_has_project_scope
from observations.models.observation import Observation


@dataclass(frozen=True)
class ObservationVerificationResult:
    """
    Result object for observation review/verification policy checks.

    MVP purpose:
    - Decide whether an actor may review, verify, or reject an observation.
    - Keep verification permission logic outside views/admin/services.
    - Prepare clean workflow services later without building them too early.

    Important architecture rule:
    Policies decide access.
    Policies do not change scientific truth.
    """

    allowed: bool
    reason: str
    capability_code: Optional[str] = None


def _check_base_verification_access(
    user,
    observation: Observation,
    organization: Optional[Organization],
    capability_code: str,
) -> ObservationVerificationResult:
    """
    Shared base check for observation review/verification actions.

    MVP rules:
    - User must have the required capability.
    - User must act through active membership/organization.
    - Acting organization must own or actively collaborate on the observation project.

    Left for later:
    - Additional workflow-state validators.
    - Audit logging for review/verify/reject actions.
    - More detailed sensitivity gates for critical records.
    """

    capability_result = check_user_capability(
        user=user,
        organization=organization,
        capability_code=capability_code,
    )

    if not capability_result.allowed:
        return ObservationVerificationResult(
            allowed=False,
            reason=capability_result.reason,
            capability_code=capability_code,
        )

    acting_organization = capability_result.context.organization

    scope_result = organization_has_project_scope(
        organization=acting_organization,
        project=observation.project,
    )

    if not scope_result.allowed:
        return ObservationVerificationResult(
            allowed=False,
            reason=scope_result.reason,
            capability_code=capability_code,
        )

    return ObservationVerificationResult(
        allowed=True,
        reason="Base observation verification access allowed.",
        capability_code=capability_code,
    )


def can_review_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationVerificationResult:
    """
    Decide whether a user can review an observation.

    MVP rules:
    - Requires review_observations.
    - Requires project scope.
    - Archived observations cannot be reviewed through MVP workflow.
    """

    if observation.observation_status == Observation.ObservationStatus.ARCHIVED:
        return ObservationVerificationResult(
            allowed=False,
            reason="Archived observations cannot be reviewed in the MVP workflow.",
            capability_code="review_observations",
        )

    return _check_base_verification_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="review_observations",
    )


def can_verify_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationVerificationResult:
    """
    Decide whether a user can verify an observation.

    MVP rules:
    - Requires verify_observations.
    - Requires project scope.
    - Archived/rejected observations cannot be verified through MVP workflow.
    - Already published observations should not be verified again here.

    Important:
    This policy only answers permission.
    Later validator/service will decide valid status transitions more strictly.
    """

    blocked_statuses = {
        Observation.ObservationStatus.ARCHIVED,
        Observation.ObservationStatus.REJECTED,
        Observation.ObservationStatus.PUBLISHED,
    }

    if observation.observation_status in blocked_statuses:
        return ObservationVerificationResult(
            allowed=False,
            reason=(
                "Observation status does not allow verification through the MVP workflow."
            ),
            capability_code="verify_observations",
        )

    return _check_base_verification_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="verify_observations",
    )


def can_reject_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationVerificationResult:
    """
    Decide whether a user can reject an observation.

    MVP rules:
    - Requires reject_observations.
    - Requires project scope.
    - Archived/published observations cannot be rejected through MVP workflow.

    Later:
    - Published observation rejection should go through revision/unpublish workflow.
    """

    blocked_statuses = {
        Observation.ObservationStatus.ARCHIVED,
        Observation.ObservationStatus.PUBLISHED,
    }

    if observation.observation_status in blocked_statuses:
        return ObservationVerificationResult(
            allowed=False,
            reason=(
                "Observation status does not allow rejection through the MVP workflow."
            ),
            capability_code="reject_observations",
        )

    return _check_base_verification_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="reject_observations",
    )


def can_reopen_observation(*, user, observation, organization=None):
    """
    Decide whether a rejected observation can be reopened for review.

    MVP purpose:
    - Reopening rejected observations is a protected scientific workflow action.
    - Reopen does not verify the observation.
    - Reopen only returns it to review workflow.

    Architecture rule:
    - Reopen changes workflow state, so it requires revise_observations.
    - This keeps policy permission aligned with service audit records.
    - Normal review still uses review_observations.
    """

    if observation.observation_status != Observation.ObservationStatus.REJECTED:
        return ObservationVerificationResult(
            allowed=False,
            reason="Only rejected observations can be reopened through this workflow.",
            capability_code="revise_observations",
        )

    return _check_base_verification_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="revise_observations",
    )

