import uuid

from django.db import models


class ProjectCollaboration(models.Model):
    """
    Formal participation link between a project and another organization.

    MVP purpose:
    - Record which organizations participate in a project.
    - Preserve collaboration role, access level, and lifecycle status.
    - Keep ownership clean: collaboration never means project ownership.

    Important architecture rule:
    ProjectCollaboration does not grant unrestricted access.
    Real access must still pass through active membership, acting organization,
    capability, scope, visibility, sensitivity, policy, and audit where required.

    Left for later:
    - Collaboration access policies.
    - Audit logging for collaboration creation/status/access-level changes.
    - Research/sponsor/grant-specific collaboration workflows.
    """

    class CollaborationRole(models.TextChoices):
        RESEARCH_PARTNER = "research_partner", "Research partner"
        FIELD_PARTNER = "field_partner", "Field partner"
        FUNDING_PARTNER = "funding_partner", "Funding partner"
        GOVERNMENT_PARTNER = "government_partner", "Government partner"
        NGO_PARTNER = "ngo_partner", "NGO partner"
        UNIVERSITY_PARTNER = "university_partner", "University partner"
        SPONSOR_PARTNER = "sponsor_partner", "Sponsor partner"
        OBSERVER = "observer", "Observer"
        OTHER = "other", "Other"

    class AccessLevel(models.TextChoices):
        PUBLIC_SAFE = "public_safe", "Public safe"
        PARTNER = "partner", "Partner"
        RESEARCH = "research", "Research"
        RESTRICTED = "restricted", "Restricted"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"
        ARCHIVED = "archived", "Archived"

    # Stable collaboration identifier for future APIs, exports, and audit trails.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="collaborations",
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="project_collaborations",
    )

    # Describes why the organization participates.
    # This is descriptive only and must not become automatic authorization logic.
    collaboration_role = models.CharField(
        max_length=40,
        choices=CollaborationRole.choices,
        default=CollaborationRole.OTHER,
    )

    # MVP descriptive access category.
    # This prepares future policy checks but does not grant permission by itself.
    access_level = models.CharField(
        max_length=30,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC_SAFE,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.INVITED,
    )

    started_at = models.DateField(blank=True, null=True)
    ended_at = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name_bs", "organization__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "organization"],
                name="unique_project_collaboration_per_organization",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["collaboration_role"]),
            models.Index(fields=["access_level"]),
        ]

    def __str__(self):
        return f"{self.organization} on {self.project}"