from dataclasses import dataclass
from typing import Optional

from organizations.models.organization import Organization

from access.services.capability_check_service import check_user_capability
from access.services.project_scope_service import organization_has_project_scope
from observations.models.observation import Observation
from observations.policies.observation_access_policy import can_view_sensitive_observation


@dataclass(frozen=True)
class ObservationPublicationResult:
    """
    Result object for observation publication policy checks.

    MVP purpose:
    - Decide whether an actor may publish or unpublish an observation.
    - Keep publication permission logic outside views/admin/services.
    - Prepare future publication services without changing scientific truth here.

    Important architecture rule:
    Policies decide access.
    Policies do not publish, unpublish, verify, or mutate Observation records.
    """

    allowed: bool
    reason: str
    capability_code: Optional[str] = None


def _check_base_publication_access(
    user,
    observation: Observation,
    organization: Optional[Organization],
    capability_code: str,
) -> ObservationPublicationResult:
    """
    Shared base check for observation publication actions.

    MVP rules:
    - User must have the required publication capability.
    - User must act through active membership/organization.
    - Acting organization must own or actively collaborate on the observation project.
    """

    capability_result = check_user_capability(
        user=user,
        organization=organization,
        capability_code=capability_code,
    )

    if not capability_result.allowed:
        return ObservationPublicationResult(
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
        return ObservationPublicationResult(
            allowed=False,
            reason=scope_result.reason,
            capability_code=capability_code,
        )

    return ObservationPublicationResult(
        allowed=True,
        reason="Base observation publication access allowed.",
        capability_code=capability_code,
    )


def _requires_sensitive_access(observation: Observation) -> bool:
    """
    Return True when the observation carries sensitivity risk.

    MVP purpose:
    - Keep sensitive publication decisions explicit.
    - Avoid publishing sensitive records without additional permission awareness.

    Left for later:
    - Dedicated publish_sensitive_observations capability if needed.
    - Coordinate redaction and public-safe publication validators.
    """

    sensitive_levels = {
        Observation.SensitivityLevel.SENSITIVE,
        Observation.SensitivityLevel.HIGHLY_SENSITIVE,
        Observation.SensitivityLevel.CRITICAL,
    }

    return observation.sensitivity_level in sensitive_levels


def can_publish_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationPublicationResult:
    """
    Decide whether a user can publish an observation.

    MVP rules:
    - Requires publish_observations.
    - Requires project scope.
    - Observation must be verified.
    - Rejected or archived observations cannot be published.
    - Already published observations should not be published again here.
    - Sensitive observations require view_sensitive_observations for now.

    Important:
    This policy only answers whether publication is allowed.
    The future publication service will perform the actual state change.
    """

    blocked_statuses = {
        Observation.ObservationStatus.REJECTED,
        Observation.ObservationStatus.ARCHIVED,
        Observation.ObservationStatus.PUBLISHED,
    }

    if observation.observation_status in blocked_statuses:
        return ObservationPublicationResult(
            allowed=False,
            reason="Observation status does not allow publication through the MVP workflow.",
            capability_code="publish_observations",
        )

    if observation.verification_status != Observation.VerificationStatus.VERIFIED:
        return ObservationPublicationResult(
            allowed=False,
            reason="Observation must be verified before publication.",
            capability_code="publish_observations",
        )

    base_result = _check_base_publication_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="publish_observations",
    )

    if not base_result.allowed:
        return base_result

    if _requires_sensitive_access(observation):
        sensitive_result = can_view_sensitive_observation(
            user=user,
            observation=observation,
            organization=organization,
        )

        if not sensitive_result.allowed:
            return ObservationPublicationResult(
                allowed=False,
                reason=(
                    "Observation is sensitive and user lacks "
                    "view_sensitive_observations."
                ),
                capability_code="view_sensitive_observations",
            )

    return ObservationPublicationResult(
        allowed=True,
        reason="Observation publication allowed.",
        capability_code="publish_observations",
    )


def can_unpublish_observation(
    user,
    observation: Observation,
    organization: Optional[Organization] = None,
) -> ObservationPublicationResult:
    """
    Decide whether a user can unpublish an observation.

    MVP rules:
    - Requires unpublish_observations.
    - Requires project scope.
    - Observation must currently be published.
    - Sensitive observations require view_sensitive_observations for now.

    Later:
    - Unpublish should create revision history.
    - Unpublish should create audit records.
    - Unpublish should require reason.
    """

    if observation.observation_status != Observation.ObservationStatus.PUBLISHED:
        return ObservationPublicationResult(
            allowed=False,
            reason="Only published observations can be unpublished.",
            capability_code="unpublish_observations",
        )

    base_result = _check_base_publication_access(
        user=user,
        observation=observation,
        organization=organization,
        capability_code="unpublish_observations",
    )

    if not base_result.allowed:
        return base_result

    if _requires_sensitive_access(observation):
        sensitive_result = can_view_sensitive_observation(
            user=user,
            observation=observation,
            organization=organization,
        )

        if not sensitive_result.allowed:
            return ObservationPublicationResult(
                allowed=False,
                reason=(
                    "Observation is sensitive and user lacks "
                    "view_sensitive_observations."
                ),
                capability_code="view_sensitive_observations",
            )

    return ObservationPublicationResult(
        allowed=True,
        reason="Observation unpublication allowed.",
        capability_code="unpublish_observations",
    )

