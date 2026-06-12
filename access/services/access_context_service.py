from dataclasses import dataclass
from typing import Optional

from organizations.models.membership import Membership
from organizations.models.organization import Organization


class AccessContextError(Exception):
    """
    Base error for RBAC access-context resolution.

    MVP purpose:
    - Keep access failures explicit.
    - Avoid hiding permission problems behind random None checks.
    """


class ActingOrganizationRequired(AccessContextError):
    """
    Raised when a user has more than one active membership and no acting
    organization was provided.

    Left for later:
    - Frontend/API acting-organization selection.
    - Session-backed acting organization.
    """


class ActiveMembershipRequired(AccessContextError):
    """
    Raised when a protected workflow requires an active membership but none exists.
    """


@dataclass(frozen=True)
class AccessContext:
    """
    Resolved RBAC context for one request/workflow.

    MVP purpose:
    - Represent who the user is acting as.
    - Carry the active membership and acting organization together.
    - Give policies/services one clean object instead of repeating lookup logic.

    Important architecture rule:
    Login proves identity only.
    Access must flow through active membership and acting organization.
    """

    user: object
    membership: Optional[Membership]
    organization: Optional[Organization]

    @property
    def has_active_membership(self) -> bool:
        return self.membership is not None

    @property
    def role(self):
        if not self.membership:
            return None
        return self.membership.role


def _is_authenticated_user(user) -> bool:
    """
    Return True only for real authenticated users.

    Anonymous users may still access future public-safe APIs,
    but they must not receive protected membership-based access.
    """

    return bool(user and getattr(user, "is_authenticated", False))


def get_active_memberships_for_user(user):
    """
    Return active memberships for an authenticated user.

    MVP scope:
    - Active membership only.
    - Active organization only.
    - Includes role and organization for efficient service checks.
    """

    if not _is_authenticated_user(user):
        return Membership.objects.none()

    return (
        Membership.objects.select_related("organization", "role")
        .filter(
            user=user,
            status=Membership.MembershipStatus.ACTIVE,
            organization__is_active=True,
        )
        .order_by("organization__name")
    )


def get_active_membership(user, organization: Optional[Organization] = None):
    """
    Resolve one active membership for a user.

    If organization is provided:
    - membership must match that organization.

    If organization is not provided:
    - zero memberships returns None.
    - one membership returns that membership.
    - multiple memberships raises ActingOrganizationRequired.

    This prevents silent permission leakage across organizations.
    """

    active_memberships = get_active_memberships_for_user(user)

    if organization is not None:
        return active_memberships.filter(organization=organization).first()

    membership_count = active_memberships.count()

    if membership_count == 0:
        return None

    if membership_count > 1:
        raise ActingOrganizationRequired(
            "User has multiple active memberships. Provide an acting organization."
        )

    return active_memberships.first()


def build_access_context(
    user,
    organization: Optional[Organization] = None,
    require_membership: bool = False,
) -> AccessContext:
    """
    Build the access context used by future policies and services.

    MVP purpose:
    - Resolve user + organization into active membership context.
    - Keep protected workflows from guessing which organization is active.

    If require_membership=True:
    - raises ActiveMembershipRequired when no active membership exists.
    """

    membership = get_active_membership(user=user, organization=organization)

    if require_membership and membership is None:
        raise ActiveMembershipRequired(
            "An active organization membership is required for this action."
        )

    resolved_organization = membership.organization if membership else organization

    return AccessContext(
        user=user,
        membership=membership,
        organization=resolved_organization,
    )