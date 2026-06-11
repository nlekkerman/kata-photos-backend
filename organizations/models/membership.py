from django.conf import settings
from django.db import models

from organizations.models.organization import Organization


class Membership(models.Model):
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