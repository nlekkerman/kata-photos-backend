from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from organizations.models import Organization


class Role(models.Model):
    """
    Human-readable RBAC role template.

    MVP purpose:
    - Groups capabilities through RoleCapability.
    - Supports global/system roles and organization-owned roles.

    Architecture rule:
    - Role names are labels only.
    - Business logic must check capabilities, not role names.
    - A role may be global/system-wide or organization-owned, but not both.

    Left for later:
    - Role/capability management workflows should audit permission changes.
    - Future scoped capabilities may add narrower project/object-level access.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="roles",
        null=True,
        blank=True,
    )

    code = models.SlugField(max_length=120)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    is_system_role = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Validate the role ownership invariant.

        Allows:
        - global/system roles with no organization
        - organization-owned roles with one organization

        Blocks:
        - organization=None with is_system_role=False
        - organization set with is_system_role=True
        """

        super().clean()

        if self.organization_id is None and not self.is_system_role:
            raise ValidationError(
                {
                    "is_system_role": (
                        "A role without an organization must be marked as a system role."
                    )
                }
            )

        if self.organization_id is not None and self.is_system_role:
            raise ValidationError(
                {
                    "is_system_role": (
                        "Organization-owned roles must not be marked as system roles."
                    )
                }
            )

    class Meta:
        ordering = ["organization__name", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_role_code_per_organization",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(organization__isnull=True),
                name="unique_system_role_code",
            ),
        ]

    def __str__(self):
        if self.organization:
            return f"{self.organization} - {self.name}"
        return f"System - {self.name}"