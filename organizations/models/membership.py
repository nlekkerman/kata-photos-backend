from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from organizations.models.organization import Organization


class Membership(models.Model):
    """
    Organization membership for one user.

    MVP purpose:
    - Connects a user to one organization.
    - Stores the user's role inside that organization.
    - Provides the first organization boundary for RBAC.

    Architecture rule:
    - Login proves identity only.
    - Membership gives organization context.
    - Real access still requires capability, scope, target object,
      visibility, sensitivity, policy, and audit where needed.

    Left for later:
    - ActorContext decides which membership/acting organization is used per request.
    - Membership role changes should be audited through management workflows.
    """

    class MembershipStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REMOVED = "removed", "Removed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    role = models.ForeignKey(
        "access.Role",
        on_delete=models.PROTECT,
        related_name="memberships",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Validate that the membership role belongs to the correct boundary.

        Allows:
        - no role yet
        - global/system role where role.organization is empty
        - role owned by the same organization as this membership

        Blocks:
        - role owned by another organization
        """

        super().clean()

        if not self.role_id:
            return

        if self.role.organization_id is None:
            return

        if self.role.organization_id != self.organization_id:
            raise ValidationError(
                {
                    "role": (
                        "Membership role must belong to the same organization "
                        "or be a valid global/system role."
                    )
                }
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            )
        ]
        ordering = ["organization__name", "user__username"]

    def __str__(self):
        return f"{self.user} - {self.organization} - {self.status}"