from dataclasses import dataclass

from projects.models.project_collaboration import ProjectCollaboration


class ProjectScopeDenied(Exception):
    """
    Raised when an acting organization has no valid project scope.
    """


@dataclass(frozen=True)
class ProjectScopeResult:
    """
    Project-scope decision result.

    MVP purpose:
    - Clearly say whether the acting organization can access the project scope.
    - Separate ownership/collaboration scope from capability checks.

    Important architecture rule:
    Project scope does not grant full access by itself.
    The actor still needs capability, policy approval, visibility/sensitivity checks,
    and audit where required.
    """

    allowed: bool
    reason: str
    relation: str


def organization_has_project_scope(organization, project) -> ProjectScopeResult:
    """
    Check whether an organization has scope for a project.

    MVP rules:
    - Owning organization has project scope.
    - Active collaboration gives project scope.
    - Collaboration does not grant unrestricted access by itself.
    """

    if organization is None:
        return ProjectScopeResult(
            allowed=False,
            reason="No acting organization provided.",
            relation="none",
        )

    if project is None:
        return ProjectScopeResult(
            allowed=False,
            reason="No project provided.",
            relation="none",
        )

    if project.owning_organization_id == organization.id:
        return ProjectScopeResult(
            allowed=True,
            reason="Organization owns this project.",
            relation="owner",
        )

    has_active_collaboration = ProjectCollaboration.objects.filter(
        project=project,
        organization=organization,
        status=ProjectCollaboration.Status.ACTIVE,
    ).exists()

    if has_active_collaboration:
        return ProjectScopeResult(
            allowed=True,
            reason="Organization has active project collaboration.",
            relation="collaborator",
        )

    return ProjectScopeResult(
        allowed=False,
        reason="Organization does not own or actively collaborate on this project.",
        relation="none",
    )


def organization_can_access_project_scope(organization, project) -> bool:
    """
    Boolean convenience wrapper for project-scope checks.
    """

    return organization_has_project_scope(
        organization=organization,
        project=project,
    ).allowed


def require_project_scope(organization, project) -> ProjectScopeResult:
    """
    Require project scope or raise ProjectScopeDenied.

    Future policies can call this before allowing project-level actions.
    """

    result = organization_has_project_scope(
        organization=organization,
        project=project,
    )

    if not result.allowed:
        raise ProjectScopeDenied(result.reason)

    return result