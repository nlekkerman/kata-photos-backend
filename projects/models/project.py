import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    """
    Canonical scientific work boundary for Kata Wild.

    MVP purpose:
    - Store the core project record.
    - Attach each project to exactly one owning organization.
    - Prepare the future Observation spine, because observations will later belong to projects.

    Important architecture rule:
    A project has one owner only. Other organizations participate through
    ProjectCollaboration, not through extra owner fields or hidden shortcuts.

    Left for later:
    - Project-scoped RBAC policy enforcement.
    - Project audit logging for ownership/status/visibility changes.
    - Observation, monitoring point, camera deployment, and evidence relationships.
    """

    class ProjectType(models.TextChoices):
        MONITORING = "monitoring", "Monitoring"
        SPECIES_SURVEY = "species_survey", "Species survey"
        FUNGI_SURVEY = "fungi_survey", "Fungi survey"
        PLANT_SURVEY = "plant_survey", "Plant survey"
        DRONE_SURVEY = "drone_survey", "Drone survey"
        CAMERA_NETWORK = "camera_network", "Camera network"
        RESEARCH = "research", "Research"
        EDUCATION = "education", "Education"
        SPONSOR_PROGRAM = "sponsor_program", "Sponsor program"
        GRANT_PROGRAM = "grant_program", "Grant program"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner"
        RESEARCH = "research", "Research"
        RESTRICTED = "restricted", "Restricted"

    # Stable internal identifier for future APIs, exports, and audit trails.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Stable project code. Names can change; code should stay stable.
    code = models.CharField(max_length=80, unique=True)

    # Routing/admin-friendly identifier. Kept separate from canonical code.
    slug = models.SlugField(max_length=120, unique=True)

    # One owning organization only.
    # This protects the locked rule: no multi-owner project ambiguity.
    owning_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="owned_projects",
    )

    # Bosnian-first naming with English as secondary.
    name_bs = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180, blank=True)

    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    # Controlled type/status fields keep project lifecycle clean and queryable.
    project_type = models.CharField(
        max_length=40,
        choices=ProjectType.choices,
        default=ProjectType.MONITORING,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNING,
    )

    # Visibility is audience-level classification.
    # It does not replace RBAC capability, scope, policy, or sensitivity checks.
    visibility_level = models.CharField(
        max_length=30,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.RESTRICTED,
    )

    # Optional MVP project time range.
    # Later validators can enforce date rules if needed.
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Creator gives basic accountability during MVP.
    # Full audit logging comes later through AuditRecord workflows.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_projects",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name_bs"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["owning_organization", "status"]),
            models.Index(fields=["project_type", "status"]),
            models.Index(fields=["visibility_level"]),
        ]

    def __str__(self):
        return self.name_bs