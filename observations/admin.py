from django.contrib import admin

from .models import (
    Observation,
    ObservationEvidenceLink,
    ObservationReview,
    ObservationRevision,
    ObservationTaxon,
)


class ObservationEvidenceLinkInline(admin.TabularInline):
    """
    Inline evidence links for MVP admin smoke testing.

    This lets us connect saved EvidenceItem records to an Observation manually
    without creating API workflows yet.
    """

    model = ObservationEvidenceLink
    extra = 1
    autocomplete_fields = ["evidence_item"]
    fields = [
        "evidence_item",
        "link_type",
        "is_primary",
        "notes",
    ]


class ObservationTaxonInline(admin.TabularInline):
    """
    Inline taxon identity records for MVP admin smoke testing.

    Uses the real Taxon model fields through autocomplete/search configured
    in the Taxon admin. Taxon itself uses canonical_display_name_bs,
    canonical_display_name_en, and scientific_name_current.
    """

    model = ObservationTaxon
    extra = 1
    autocomplete_fields = ["taxon", "identified_by"]
    fields = [
        "taxon",
        "identification_status",
        "confidence_level",
        "life_stage",
        "sex",
        "count_min",
        "count_max",
        "identified_by",
        "identified_at",
        "behavior_notes_bs",
        "behavior_notes_en",
    ]


class ObservationReviewInline(admin.TabularInline):
    """
    Inline manual review trail for MVP admin smoke testing.

    Full verification services and audit integration come later.
    """

    model = ObservationReview
    extra = 1
    autocomplete_fields = ["reviewed_by"]
    fields = [
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "review_notes",
    ]

class ObservationRevisionInline(admin.TabularInline):
    """
    Inline revision trail for MVP admin smoke testing.

    Full automatic revision creation and audit integration come later.
    """

    model = ObservationRevision
    extra = 1
    autocomplete_fields = ["changed_by"]
    fields = [
        "revision_type",
        "changed_by",
        "reason",
        "previous_observation_status",
        "new_observation_status",
        "previous_verification_status",
        "new_verification_status",
        "previous_taxon_summary",
        "new_taxon_summary",
        "notes",
        "created_at",
    ]
    readonly_fields = ["created_at"]


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    """
    Django admin management for canonical Observation records.

    MVP purpose:
    - Manually smoke-test Observation creation.
    - Link Observation to project, monitoring context, evidence, taxon, and review.
    - Keep workflows visible before APIs/services are introduced.
    """

    list_display = [
        "code",
        "project",
        "observation_type",
        "observation_status",
        "verification_status",
        "recorded_at",
        "sensitivity_level",
        "visibility_level",
    ]

    list_filter = [
        "observation_type",
        "observation_status",
        "verification_status",
        "sensitivity_level",
        "visibility_level",
        "project",
        "location_zone",
        "habitat",
    ]

    search_fields = [
        "code",
        "public_location_label_bs",
        "public_location_label_en",
        "notes_public_bs",
        "notes_public_en",
        "notes_private",
        "taxon_links__taxon__canonical_display_name_bs",
        "taxon_links__taxon__canonical_display_name_en",
        "taxon_links__taxon__scientific_name_current",
        "evidence_links__evidence_item__code",
    ]

    autocomplete_fields = [
        "project",
        "monitoring_point",
        "location_zone",
        "habitat",
        "camera_deployment",
        "created_by",
        "verified_by",
    ]

    readonly_fields = [
        "uuid",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Core scientific truth",
            {
                "fields": (
                    "uuid",
                    "code",
                    "project",
                    "observation_type",
                    "observation_status",
                    "verification_status",
                    "recorded_at",
                    "observed_started_at",
                    "observed_ended_at",
                )
            },
        ),
        (
            "Canonical context",
            {
                "fields": (
                    "monitoring_point",
                    "location_zone",
                    "habitat",
                    "camera_deployment",
                )
            },
        ),
        (
            "Visibility and sensitivity",
            {
                "fields": (
                    "sensitivity_level",
                    "visibility_level",
                    "public_location_label_bs",
                    "public_location_label_en",
                    "public_location_precision",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes_public_bs",
                    "notes_public_en",
                    "notes_private",
                )
            },
        ),
        (
            "Human verification",
            {
                "fields": (
                    "created_by",
                    "verified_by",
                    "verified_at",
                )
            },
        ),
        (
            "System timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = [
        ObservationEvidenceLinkInline,
        ObservationTaxonInline,
        ObservationReviewInline,
        ObservationRevisionInline,
        
    ]


@admin.register(ObservationEvidenceLink)
class ObservationEvidenceLinkAdmin(admin.ModelAdmin):
    """
    Standalone admin for Observation-Evidence links.

    Useful for checking evidence support records outside the Observation inline.
    """

    list_display = [
        "observation",
        "evidence_item",
        "link_type",
        "is_primary",
        "created_at",
    ]

    list_filter = [
        "link_type",
        "is_primary",
    ]

    search_fields = [
        "observation__code",
        "evidence_item__code",
        "notes",
    ]

    autocomplete_fields = [
        "observation",
        "evidence_item",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(ObservationTaxon)
class ObservationTaxonAdmin(admin.ModelAdmin):
    """
    Standalone admin for Observation taxon identity records.

    Search uses the real Taxon fields:
    canonical_display_name_bs, canonical_display_name_en, scientific_name_current.
    """

    list_display = [
        "observation",
        "taxon",
        "identification_status",
        "confidence_level",
        "life_stage",
        "sex",
        "count_min",
        "count_max",
    ]

    list_filter = [
        "identification_status",
        "confidence_level",
        "life_stage",
        "sex",
    ]

    search_fields = [
        "observation__code",
        "taxon__canonical_display_name_bs",
        "taxon__canonical_display_name_en",
        "taxon__scientific_name_current",
        "behavior_notes_bs",
        "behavior_notes_en",
    ]

    autocomplete_fields = [
        "observation",
        "taxon",
        "identified_by",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(ObservationReview)
class ObservationReviewAdmin(admin.ModelAdmin):
    """
    Standalone admin for manual Observation review records.

    MVP only. Later verification decisions should go through a service and audit.
    """

    list_display = [
        "observation",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    ]

    list_filter = [
        "review_status",
    ]

    search_fields = [
        "observation__code",
        "review_notes",
    ]

    autocomplete_fields = [
        "observation",
        "reviewed_by",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

@admin.register(ObservationRevision)
class ObservationRevisionAdmin(admin.ModelAdmin):
    """
    Standalone admin for Observation revision/history records.

    MVP purpose:
    - Manually preserve scientific correction history.
    - Keep changes reviewable before automatic services/audit exist.
    """

    list_display = [
        "observation",
        "revision_type",
        "changed_by",
        "created_at",
    ]

    list_filter = [
        "revision_type",
        "created_at",
    ]

    search_fields = [
        "observation__code",
        "reason",
        "previous_taxon_summary",
        "new_taxon_summary",
        "notes",
    ]

    autocomplete_fields = [
        "observation",
        "changed_by",
    ]

    readonly_fields = [
        "created_at",
    ]