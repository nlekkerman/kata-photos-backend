from django.db.models import QuerySet

from locations.models.monitoring_point import MonitoringPoint


def get_public_monitoring_points() -> QuerySet[MonitoringPoint]:
    """
    Return monitoring points that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public monitoring points.
    - Exclude retired/archived/non-active monitoring points.
    - Exclude sensitive or restricted monitoring points.
    - Prevent public views from accidentally exposing exact monitoring locations.

    Architecture rule:
    - MonitoringPoint is a permanent scientific monitoring place.
    - Private latitude/longitude are protected scientific data.
    - Public selectors must use public labels/precision only, not private coordinates.

    Important current limitation:
    - MonitoringPoint does not currently have an is_public field.
    - Public eligibility is therefore derived conservatively from active status
      and non-sensitive sensitivity level until an explicit public flag exists later.

    Left for later:
    - Explicit public visibility flag if needed.
    - Public-safe approximate coordinate selector.
    - Workspace/research selectors with scoped RBAC and audit.
    """

    return (
        MonitoringPoint.objects.filter(
            status=MonitoringPoint.Status.ACTIVE,
            sensitivity_level=MonitoringPoint.SensitivityLevel.NORMAL,
        )
        .select_related(
            "project",
            "location_zone",
            "primary_habitat",
        )
        .order_by("project__name_bs", "name_bs")
    )


def get_public_monitoring_point_by_slug(slug: str) -> MonitoringPoint | None:
    """
    Return one public-safe monitoring point by slug.

    MVP purpose:
    - Give future public detail APIs a safe lookup helper.
    - Return None instead of leaking inactive or sensitive monitoring points.

    Architecture rule:
    - Public monitoring-point lookup must use the same safety rules as public lists.
    """

    return get_public_monitoring_points().filter(slug=slug).first()