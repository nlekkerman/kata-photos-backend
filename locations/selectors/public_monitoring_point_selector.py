from django.db.models import QuerySet

from locations.models.monitoring_point import MonitoringPoint


def get_public_monitoring_points() -> QuerySet[MonitoringPoint]:
    """
    Return monitoring points that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public monitoring points.
    - Exclude private, sensitive, hidden, retired, and archived monitoring points.
    - Prevent public views from accidentally exposing exact monitoring locations.

    Architecture rule:
    - MonitoringPoint is a permanent scientific monitoring place.
    - Private coordinates are protected scientific data.
    - Public APIs must not expose private latitude/longitude or private notes.

    Left for later:
    - Public-safe approximate coordinate selector.
    - Workspace/research selectors with scoped RBAC and audit.
    - Project-specific public monitoring maps.
    """

    return (
        MonitoringPoint.objects.filter(
            is_public=True,
            status=MonitoringPoint.Status.ACTIVE,
        )
        .exclude(
            sensitivity_level__in=[
                MonitoringPoint.SensitivityLevel.SENSITIVE,
                MonitoringPoint.SensitivityLevel.RESTRICTED,
            ]
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
    - Return None instead of leaking non-public or sensitive monitoring points.

    Architecture rule:
    - Public monitoring-point lookup must use the same safety rules as public lists.
    """

    return get_public_monitoring_points().filter(slug=slug).first()