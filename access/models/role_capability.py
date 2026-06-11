from django.db import models

from access.models.capability import Capability
from access.models.role import Role


class RoleCapability(models.Model):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_capabilities",
    )

    capability = models.ForeignKey(
        Capability,
        on_delete=models.CASCADE,
        related_name="role_capabilities",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role__code", "capability__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "capability"],
                name="unique_capability_per_role",
            )
        ]
        verbose_name = "Role capability"
        verbose_name_plural = "Role capabilities"

    def __str__(self):
        return f"{self.role} -> {self.capability}"