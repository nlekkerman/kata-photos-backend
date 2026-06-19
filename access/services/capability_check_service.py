from dataclasses import dataclass
from typing import Optional

from access.models.role_capability import RoleCapability
from organizations.models.organization import Organization

from .access_context_service import (
    AccessContext,
    ActingOrganizationRequired,
    build_access_context,
)


class CapabilityDenied(Exception):
    """
    Raised when a user does not have the required capability.

    MVP purpose:
    - Give future services/policies one explicit denial exception.
    - Avoid scattered permission error strings.
    """


@dataclass(frozen=True)
class CapabilityCheckResult:
    """
    Result object for capability checks.

    MVP purpose:
    - Return allow/deny plus a clear reason.
    - Keep debugging simple while RBAC enforcement grows.
    """

    allowed: bool
    capability_code: str
    reason: str
    context: AccessContext


def membership_has_capability(membership, capability_code: str) -> bool:
    """
    Check whether a membership's role has an active capability.

    MVP scope:
    - One role per membership.
    - Role must be active.
    - Capability must be active.
    - Capability matched by canonical code.

    Architecture rule:
    - This assumes Membership.role integrity is enforced by the Membership model.
    - Capability checks must not depend on human role names.

    Left for later:
    - Multiple roles per membership if needed.
    - Direct membership capability overrides.
    - Scoped capability assignments.
    """

    if not membership:
        return False

    if not membership.role:
        return False

    if not membership.role.is_active:
        return False

    return RoleCapability.objects.filter(
        role=membership.role,
        capability__code=capability_code,
        capability__is_active=True,
    ).exists()


def check_user_capability(
    user,
    capability_code: str,
    organization: Optional[Organization] = None,
) -> CapabilityCheckResult:
    """
    Safely check whether the user has a capability in one organization context.

    MVP purpose:
    - Return a result object instead of raising for normal permission denial.
    - Keep boolean helpers safe for views, policies, and manual smoke tests.
    - Make multi-organization ambiguity visible without causing surprise 500s.

    Architecture rule:
    - This checks capability vocabulary only.
    - It does not check project scope, target object, visibility, sensitivity,
      publication state, or audit requirements.
    - Protected workflows must compose this with project/object-specific policies.
    """

    try:
        context = build_access_context(
            user=user,
            organization=organization,
            require_membership=False,
        )
    except ActingOrganizationRequired as exc:
        return CapabilityCheckResult(
            allowed=False,
            capability_code=capability_code,
            reason=str(exc),
            context=AccessContext(
                user=user,
                membership=None,
                organization=organization,
            ),
        )

    if not context.membership:
        return CapabilityCheckResult(
            allowed=False,
            capability_code=capability_code,
            reason="No active membership found.",
            context=context,
        )

    if not context.role:
        return CapabilityCheckResult(
            allowed=False,
            capability_code=capability_code,
            reason="Active membership has no role.",
            context=context,
        )

    if not context.role.is_active:
        return CapabilityCheckResult(
            allowed=False,
            capability_code=capability_code,
            reason="Membership role is inactive.",
            context=context,
        )

    allowed = membership_has_capability(
        membership=context.membership,
        capability_code=capability_code,
    )

    if not allowed:
        return CapabilityCheckResult(
            allowed=False,
            capability_code=capability_code,
            reason=f"Role does not have capability '{capability_code}'.",
            context=context,
        )

    return CapabilityCheckResult(
        allowed=True,
        capability_code=capability_code,
        reason="Capability allowed.",
        context=context,
    )


def user_has_capability(
    user,
    capability_code: str,
    organization: Optional[Organization] = None,
) -> bool:
    """
    Boolean convenience wrapper for simple capability checks.

    Important:
    - This must stay safe and return False for normal denial/ambiguity.
    - Use require_user_capability() when a service wants an exception.
    """

    return check_user_capability(
        user=user,
        capability_code=capability_code,
        organization=organization,
    ).allowed


def require_user_capability(
    user,
    capability_code: str,
    organization: Optional[Organization] = None,
) -> CapabilityCheckResult:
    """
    Require a capability or raise CapabilityDenied.

    Future services can use this before changing canonical truth.

    Important:
    - This raises only after check_user_capability() returns a denied result.
    - Multi-organization ambiguity becomes a clear CapabilityDenied reason.
    - Project scope, visibility, sensitivity, and audit still belong in policies.
    """

    result = check_user_capability(
        user=user,
        capability_code=capability_code,
        organization=organization,
    )

    if not result.allowed:
        raise CapabilityDenied(result.reason)

    return result

