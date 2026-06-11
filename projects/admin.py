from django.contrib import admin

from projects.models import Project, ProjectCollaboration


class ProjectCollaborationInline(admin.TabularInline):
    """
    Inline view of collaborating organizations on a project admin page.

    MVP purpose:
    - Let admins see project participation from the project screen.
    - Keep collaboration visibly separate from ownership.
    - Avoid pretending collaborators are project owners.

    Left for later:
    - Capability-based admin restrictions.
    - Audit logging for collaboration changes.
    - Richer collaboration agreement fields.
    """

    model = ProjectCollaboration
    extra = 0
    fields = (
        "organization",
        "collaboration_role",
        "access_level",
        "status",
        "started_at",
        "ended_at",
    )


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Django admin management for canonical Project records.

    MVP purpose:
    - Support manual backend setup while the canonical data model is being built.
    - Keep project ownership explicit through owning_organization.
    - Keep visibility/status/type controlled through choices.

    Important:
    Django admin access itself is not the final application authorization model.
    Real protected workflows will later use backend policies and capabilities.
    """

    list_display = (
        "name_bs",
        "code",
        "owning_organization",
        "project_type",
        "status",
        "visibility_level",
        "created_at",
    )
    list_filter = (
        "project_type",
        "status",
        "visibility_level",
        "owning_organization",
    )
    search_fields = (
        "name_bs",
        "name_en",
        "code",
        "slug",
        "owning_organization__name",
    )
    prepopulated_fields = {
        "slug": ("name_bs",),
    }
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fields = (
        "uuid",
        "code",
        "slug",
        "owning_organization",
        "name_bs",
        "name_en",
        "description_bs",
        "description_en",
        "project_type",
        "status",
        "visibility_level",
        "start_date",
        "end_date",
        "created_by",
        "created_at",
        "updated_at",
    )
    inlines = [
        ProjectCollaborationInline,
    ]


@admin.register(ProjectCollaboration)
class ProjectCollaborationAdmin(admin.ModelAdmin):
    """
    Django admin management for project collaboration records.

    MVP purpose:
    - Allow manual creation/review of project participation records.
    - Preserve the locked rule that collaboration is separate from ownership.
    - Make status and descriptive access level visible for review.

    Important:
    access_level is descriptive during MVP. It is not a permission bypass.
    """

    list_display = (
        "project",
        "organization",
        "collaboration_role",
        "access_level",
        "status",
        "started_at",
        "ended_at",
    )
    list_filter = (
        "collaboration_role",
        "access_level",
        "status",
        "project",
        "organization",
    )
    search_fields = (
        "project__name_bs",
        "project__code",
        "organization__name",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fields = (
        "uuid",
        "project",
        "organization",
        "collaboration_role",
        "access_level",
        "status",
        "started_at",
        "ended_at",
        "created_at",
        "updated_at",
    )