from django.db import models

from organizations.models import Organization


class Role(models.Model):
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

    class Meta:
        ordering = ["organization__name", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_role_code_per_organization",
            )
        ]

    def __str__(self):
        if self.organization:
            return f"{self.organization} - {self.name}"
        return f"System - {self.name}"