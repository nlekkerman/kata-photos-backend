from dataclasses import dataclass

from observations.models.observation import Observation


class ObservationTransitionValidationError(Exception):
    """
    Raised when an observation workflow transition is not valid.

    MVP purpose:
    - Keep invalid scientific workflow transitions explicit.
    - Prevent services from silently moving observations through impossible states.
    """


@dataclass(frozen=True)
class ObservationTransitionValidationResult:
    """
    Result object for observation workflow transition validation.

    MVP purpose:
    - Keep validator results predictable.
    - Allow services to raise clean errors with useful reasons.
    """

    valid: bool
    reason: str


def validate_observation_transition(
    *,
    observation: Observation,
    new_observation_status: str,
    new_verification_status: str,
) -> ObservationTransitionValidationResult:
    """
    Validate whether an Observation can move from its current workflow state
    to the requested new state.

    Important architecture rule:
    Validators protect data/workflow rules.
    Validators do not check user permissions.
    Policies decide access.
    Services change truth.

    MVP allowed transitions:
    - verified/verified -> published/verified
    - published/verified -> verified/verified
    - verified/verified -> rejected/rejected
    - in_review/review_needed -> verified/verified
    - rejected/rejected -> in_review/review_needed

    Left for later:
    - draft -> submitted
    - submitted -> in_review
    - uncertain review workflow
    - archive workflow
    - revise/reopen rules with reason categories
    """

    current_observation_status = observation.observation_status
    current_verification_status = observation.verification_status

    allowed_transitions = {
        (
            Observation.ObservationStatus.VERIFIED,
            Observation.VerificationStatus.VERIFIED,
            Observation.ObservationStatus.PUBLISHED,
            Observation.VerificationStatus.VERIFIED,
        ),
        (
            Observation.ObservationStatus.PUBLISHED,
            Observation.VerificationStatus.VERIFIED,
            Observation.ObservationStatus.VERIFIED,
            Observation.VerificationStatus.VERIFIED,
        ),
        (
            Observation.ObservationStatus.VERIFIED,
            Observation.VerificationStatus.VERIFIED,
            Observation.ObservationStatus.REJECTED,
            Observation.VerificationStatus.REJECTED,
        ),
        (
            Observation.ObservationStatus.IN_REVIEW,
            Observation.VerificationStatus.REVIEW_NEEDED,
            Observation.ObservationStatus.VERIFIED,
            Observation.VerificationStatus.VERIFIED,
        ),
        (
            Observation.ObservationStatus.REJECTED,
            Observation.VerificationStatus.REJECTED,
            Observation.ObservationStatus.IN_REVIEW,
            Observation.VerificationStatus.REVIEW_NEEDED,
        ),
    }

    requested_transition = (
        current_observation_status,
        current_verification_status,
        new_observation_status,
        new_verification_status,
    )

    if requested_transition not in allowed_transitions:
        return ObservationTransitionValidationResult(
            valid=False,
            reason=(
                "Observation transition is not allowed through the MVP workflow: "
                f"{current_observation_status}/{current_verification_status} -> "
                f"{new_observation_status}/{new_verification_status}."
            ),
        )

    return ObservationTransitionValidationResult(
        valid=True,
        reason="Observation transition allowed.",
    )


def require_observation_transition(
    *,
    observation: Observation,
    new_observation_status: str,
    new_verification_status: str,
) -> None:
    """
    Raise a clear validation error if the requested transition is not valid.

    MVP purpose:
    - Keep services small.
    - Avoid repeating transition error handling in every workflow service.
    """

    result = validate_observation_transition(
        observation=observation,
        new_observation_status=new_observation_status,
        new_verification_status=new_verification_status,
    )

    if not result.valid:
        raise ObservationTransitionValidationError(result.reason)


__all__ = [
    "ObservationTransitionValidationError",
    "ObservationTransitionValidationResult",
    "require_observation_transition",
    "validate_observation_transition",
]