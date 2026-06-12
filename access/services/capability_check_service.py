from dataclasses import dataclass
from typing import Optional

from access.models.role_capability import RoleCapability
from organizations.models.organization import Organization

from .access_context_service import AccessContext, build_access_context


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
    Check whether the user has a capability in the active organization context.

    This checks capability vocabulary only.
    It does not yet check project scope, visibility, sensitivity, target object,
    or audit requirements. Those belong in policies and scope services.
    """

    context = build_access_context(
        user=user,
        organization=organization,
        require_membership=False,
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
    """

    result = check_user_capability(
        user=user,
        capability_code=capability_code,
        organization=organization,
    )

    if not result.allowed:
        raise CapabilityDenied(result.reason)

    return result