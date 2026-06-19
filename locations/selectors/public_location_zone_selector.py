from django.db.models import QuerySet

from locations.models.location_zone import LocationZone


def get_public_location_zones() -> QuerySet[LocationZone]:
    """
    Return location zones that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public location zones.
    - Exclude non-public, restricted, hidden-precision, and highly sensitive zones.
    - Prevent public views from accidentally exposing protected location context.

    Architecture rule:
    - LocationZone is canonical location context, not a frontend map label.
    - Public APIs must not decide location safety inline.
    - Private coordinates/geometry must never be exposed by public selectors.

    Left for later:
    - Public-safe geometry simplification.
    - Project-specific public location filtering.
    - Audited workspace/research selectors for protected locations.
    """

    return (
        LocationZone.objects.filter(
            is_public=True,
            visibility_level=LocationZone.VisibilityLevel.PUBLIC,
        )
        .exclude(precision_level=LocationZone.PrecisionLevel.HIDDEN)
        .exclude(
            sensitivity_level__in=[
                LocationZone.SensitivityLevel.HIGHLY_SENSITIVE,
                LocationZone.SensitivityLevel.CRITICAL,
            ]
        )
        .select_related("parent_zone")
        .order_by("name_bs")
    )


def get_public_location_zone_by_slug(slug: str) -> LocationZone | None:
    """
    Return one public-safe location zone by slug.

    MVP purpose:
    - Give future public detail APIs a safe lookup helper.
    - Return None instead of leaking restricted or sensitive location zones.

    Architecture rule:
    - Public location lookup must use the same safety rules as public location lists.
    """

    return get_public_location_zones().filter(slug=slug).first()