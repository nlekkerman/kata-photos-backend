from django.contrib import admin

from locations.models import Habitat, LocationZone, MonitoringPoint


@admin.register(LocationZone)
class LocationZoneAdmin(admin.ModelAdmin):
    """
    Django admin management for canonical LocationZone records.

    MVP purpose:
    - Create reusable location hierarchy records for regions, areas, corridors, and zones.
    - Keep public-safe labels separate from private/internal geography.

    Important:
    Private geometry and private coordinates are protected data.
    Public exposure will later go through selectors, policies, sensitivity rules, and audit.
    """

    list_display = (
        "name_bs",
        "code",
        "zone_type",
        "parent_zone",
        "visibility_level",
        "sensitivity_level",
        "is_public",
    )
    list_filter = (
        "zone_type",
        "visibility_level",
        "sensitivity_level",
        "precision_level",
        "is_public",
    )
    search_fields = (
        "name_bs",
        "name_en",
        "public_label_bs",
        "public_label_en",
        "code",
        "slug",
    )
    autocomplete_fields = (
        "parent_zone",
    )
    prepopulated_fields = {
        "slug": ("name_bs",),
    }
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "uuid",
                    "code",
                    "slug",
                    "parent_zone",
                    "zone_type",
                )
            },
        ),
        (
            "Names and public labels",
            {
                "fields": (
                    "name_bs",
                    "name_en",
                    "public_label_bs",
                    "public_label_en",
                )
            },
        ),
        (
            "Descriptions",
            {
                "fields": (
                    "description_bs",
                    "description_en",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Geometry and centers",
            {
                "fields": (
                    "public_geometry",
                    "private_geometry",
                    "public_center_latitude",
                    "public_center_longitude",
                    "private_center_latitude",
                    "private_center_longitude",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Visibility and sensitivity",
            {
                "fields": (
                    "precision_level",
                    "visibility_level",
                    "sensitivity_level",
                    "is_public",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(Habitat)
class HabitatAdmin(admin.ModelAdmin):
    """
    Django admin management for canonical Habitat records.

    MVP purpose:
    - Create reusable habitat categories for monitoring points and future observations.
    - Avoid loose habitat text scattered across unrelated models.
    """

    list_display = (
        "name_bs",
        "code",
        "habitat_type",
        "parent_habitat",
        "is_published",
    )
    list_filter = (
        "habitat_type",
        "is_published",
    )
    search_fields = (
        "name_bs",
        "name_en",
        "code",
        "slug",
    )
    autocomplete_fields = (
        "parent_habitat",
    )
    prepopulated_fields = {
        "slug": ("name_bs",),
    }
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )


@admin.register(MonitoringPoint)
class MonitoringPointAdmin(admin.ModelAdmin):
    """
    Django admin management for permanent MonitoringPoint records.

    MVP purpose:
    - Manually create fixed scientific monitoring points.
    - Connect them to project, location zone, and habitat context.

    Important:
    Monitoring points do not move.
    Private coordinates are protected data and will later require policy/audit-controlled access.
    """

    list_display = (
        "name_bs",
        "code",
        "project",
        "location_zone",
        "primary_habitat",
        "status",
        "sensitivity_level",
    )
    list_filter = (
        "status",
        "sensitivity_level",
        "public_location_precision",
        "project",
        "location_zone",
        "primary_habitat",
    )
    search_fields = (
        "name_bs",
        "name_en",
        "code",
        "slug",
        "project__name_bs",
        "location_zone__name_bs",
        "primary_habitat__name_bs",
    )
    autocomplete_fields = (
        "project",
        "location_zone",
        "primary_habitat",
    )
    prepopulated_fields = {
        "slug": ("name_bs",),
    }
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "uuid",
                    "code",
                    "slug",
                    "project",
                    "location_zone",
                    "primary_habitat",
                )
            },
        ),
        (
            "Names and purpose",
            {
                "fields": (
                    "name_bs",
                    "name_en",
                    "purpose",
                )
            },
        ),
        (
            "Private coordinates",
            {
                "fields": (
                    "private_latitude",
                    "private_longitude",
                    "elevation_meters",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Public location display",
            {
                "fields": (
                    "public_location_label_bs",
                    "public_location_label_en",
                    "public_location_precision",
                )
            },
        ),
        (
            "Status and sensitivity",
            {
                "fields": (
                    "status",
                    "sensitivity_level",
                    "started_at",
                    "retired_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )