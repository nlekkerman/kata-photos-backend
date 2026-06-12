from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from organizations.models.organization import Organization
from observations.models.observation import Observation
from observations.models.observation_revision import ObservationRevision
from observations.policies.observation_publication_policy import (
    can_publish_observation,
    can_unpublish_observation,
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
    - Update the canonical Observation status to published.
    - Create an ObservationRevision record.

    Important architecture rule:
    Services change truth.
    Policies decide access.
    This service must not bypass policy.

    Left for later:
    - Dedicated publication validator.
    - AuditRecord creation.
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

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status

    observation.observation_status = Observation.ObservationStatus.PUBLISHED

    observation.save(
        update_fields=[
            "observation_status",
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
    - Update the canonical Observation status from published back to verified.
    - Create an ObservationRevision record.

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

    previous_observation_status = observation.observation_status
    previous_verification_status = observation.verification_status

    observation.observation_status = Observation.ObservationStatus.VERIFIED

    observation.save(
        update_fields=[
            "observation_status",
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

    return ObservationPublicationServiceResult(
        observation=observation,
        revision=revision,
    )