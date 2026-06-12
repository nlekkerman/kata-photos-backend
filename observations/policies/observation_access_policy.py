from dataclasses import dataclass
from typing import Optional

from organizations.models.organization import Organization

from access.services.capability_check_service import check_user_capability
from access.services.project_scope_service import organization_has_project_scope
from observations.models.observation import Observation


@dataclass(frozen=True)
class ObservationAccessResult:
    """
    Result object for observation access policy checks.

    MVP purpose:
    - Return allow/deny with a clear reason.
    - Keep future services, selectors, and APIs from duplicating RBAC logic.
    - Make permission debugging readable during manual backend development.
    """

    allowed: bool
    reason: str
    capability_code: Optional[str] = None


def _check_base_observation_access(
    user,
    observation: Observation,
    organization: Optional[Organization],
    capability_code: str,
) -> ObservationAccessResult:
    """
    Shared base check for protected observation access.

    MVP rules:
    - User must have required capability.
    - User must act through an active membership/organization.
    - Acting organization must own or actively collaborate on the observation project.

    Important architecture rule:
    This policy does not define scientific truth.
    It only decides whether the actor may access the observation.
    """

    capability_result = check_user_capability(
        user=user,
        organization=organization,
        capability_code=capability_code,
    )

    if not capability_result.allowed:
        return ObservationAccessResult(
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
        return ObservationAccessResult(
            allowed=False,
            reason=scope_result.reason,
            capability_code=capability_code,
        )

    return ObservationAccessResult(
        allowed=True,
        reason="Base observation access allowed.",
        capability_code=capability_code,
    )


def can_view_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationAccessResult:
    """
    Decide whether a user can view an observation.

    MVP rules:
    - Requires view_observations.
    - Requires project scope.
    - Rejected observations require view_rejected_observations.
    - Unpublished/draft/review observations require view_unpublished_observations.
    - Sensitive/highly sensitive/critical observations require view_sensitive_observations.

    Left for later:
    - Public-safe observation selector.
    - Research/export access modes.
    - Exact coordinate redaction policy.
    - Audit logging for sensitive reads.
    """

    base_result = _check_base_observation_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="view_observations",
    )

    if not base_result.allowed:
        return base_result

    if observation.observation_status == Observation.ObservationStatus.REJECTED:
        rejected_result = _check_base_observation_access(
            user=user,
            observation=observation,
            organization=organization,
            capability_code="view_rejected_observations",
        )

        if not rejected_result.allowed:
            return ObservationAccessResult(
                allowed=False,
                reason="Observation is rejected and user lacks view_rejected_observations.",
                capability_code="view_rejected_observations",
            )

    unpublished_statuses = {
        Observation.ObservationStatus.DRAFT,
        Observation.ObservationStatus.SUBMITTED,
        Observation.ObservationStatus.IN_REVIEW,
        Observation.ObservationStatus.VERIFIED,
    }

    if observation.observation_status in unpublished_statuses:
        unpublished_result = _check_base_observation_access(
            user=user,
            observation=observation,
            organization=organization,
            capability_code="view_unpublished_observations",
        )

        if not unpublished_result.allowed:
            return ObservationAccessResult(
                allowed=False,
                reason=(
                    "Observation is not published and user lacks "
                    "view_unpublished_observations."
                ),
                capability_code="view_unpublished_observations",
            )

    sensitive_levels = {
        Observation.SensitivityLevel.SENSITIVE,
        Observation.SensitivityLevel.HIGHLY_SENSITIVE,
        Observation.SensitivityLevel.CRITICAL,
    }

    if observation.sensitivity_level in sensitive_levels:
        sensitive_result = can_view_sensitive_observation(
            user=user,
            observation=observation,
            organization=organization,
        )

        if not sensitive_result.allowed:
            return sensitive_result

    return ObservationAccessResult(
        allowed=True,
        reason="Observation view allowed.",
        capability_code="view_observations",
    )


def can_view_sensitive_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationAccessResult:
    """
    Decide whether a user can view sensitive observation details.

    MVP rules:
    - Requires view_sensitive_observations.
    - Requires project scope.

    Important:
    This does not yet allow exact coordinate access. Exact coordinates need their
    own future capability/policy such as view_private_coordinates.
    """

    return _check_base_observation_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="view_sensitive_observations",
    )


def can_view_observation_revisions(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationAccessResult:
    """
    Decide whether a user can view observation revision/history records.

    MVP rules:
    - Requires view_observation_revisions.
    - Requires project scope.
    - Sensitive observations still require view_sensitive_observations.
    """

    base_result = _check_base_observation_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="view_observation_revisions",
    )

    if not base_result.allowed:
        return base_result

    sensitive_levels = {
        Observation.SensitivityLevel.SENSITIVE,
        Observation.SensitivityLevel.HIGHLY_SENSITIVE,
        Observation.SensitivityLevel.CRITICAL,
    }

    if observation.sensitivity_level in sensitive_levels:
        sensitive_result = can_view_sensitive_observation(
            user=user,
            observation=observation,
            organization=organization,
        )

        if not sensitive_result.allowed:
            return sensitive_result

    return ObservationAccessResult(
        allowed=True,
        reason="Observation revisions view allowed.",
        capability_code="view_observation_revisions",
    )