from django.contrib import admin

from .models import EvidenceFile, EvidenceItem, EvidenceTaxonLink


class EvidenceFileInline(admin.TabularInline):
    """
    Inline file references for the evidence admin page.

    MVP scope:
    lets us manually attach one or more file/media references to an evidence
    record without building upload workflows yet.
    """

    model = EvidenceFile
    extra = 1
    fields = (
        "file_type",
        "storage_provider",
        "original_filename",
        "storage_key",
        "external_url",
        "mime_type",
        "file_size_bytes",
        "duration_seconds",
        "width",
        "height",
        "is_primary",
    )


class EvidenceTaxonLinkInline(admin.TabularInline):
    """
    Inline possible taxon identifications for evidence.

    This remains evidence-level identification only. It does not create final
    Observation truth.
    """

    model = EvidenceTaxonLink
    extra = 1
    autocomplete_fields = ("taxon", "identified_by")
    fields = (
        "taxon",
        "identification_status",
        "confidence_level",
        "identified_by",
        "identified_at",
        "notes",
    )


@admin.register(EvidenceItem)
class EvidenceItemAdmin(admin.ModelAdmin):
    """
    Admin interface for manual MVP evidence smoke testing.

    This admin intentionally keeps evidence, files, and possible taxon links
    together so we can verify the canonical chain before building APIs.
    """

    list_display = (
        "code",
        "title_bs",
        "project",
        "evidence_type",
        "source_type",
        "status",
        "sensitivity_level",
        "visibility_level",
        "recorded_at",
        "created_by",
    )

    list_filter = (
        "evidence_type",
        "source_type",
        "status",
        "sensitivity_level",
        "visibility_level",
        "project",
    )

    search_fields = (
        "code",
        "title_bs",
        "title_en",
        "description_bs",
        "description_en",
        "notes_private",
    )

    autocomplete_fields = (
        "project",
        "monitoring_point",
        "camera_deployment",
        "created_by",
    )

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
                    "project",
                    "created_by",
                )
            },
        ),
        (
            "Scientific context",
            {
                "fields": (
                    "monitoring_point",
                    "camera_deployment",
                    "evidence_type",
                    "source_type",
                    "status",
                    "sensitivity_level",
                    "visibility_level",
                )
            },
        ),
        (
            "Time",
            {
                "fields": (
                    "recorded_at",
                    "capture_started_at",
                    "capture_ended_at",
                )
            },
        ),
        (
            "Public/internal text",
            {
                "fields": (
                    "title_bs",
                    "title_en",
                    "description_bs",
                    "description_en",
                    "notes_private",
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

    inlines = (
        EvidenceFileInline,
        EvidenceTaxonLinkInline,
    )


@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    """
    Standalone admin for evidence file references.

    Usually files are edited inline through EvidenceItem, but this list helps
    inspect all stored references during MVP smoke testing.
    """

    list_display = (
        "evidence_item",
        "file_type",
        "storage_provider",
        "original_filename",
        "is_primary",
        "created_at",
    )

    list_filter = (
        "file_type",
        "storage_provider",
        "is_primary",
    )

    search_fields = (
        "evidence_item__code",
        "original_filename",
        "storage_key",
        "external_url",
        "checksum",
    )

    autocomplete_fields = ("evidence_item",)

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )


@admin.register(EvidenceTaxonLink)
class EvidenceTaxonLinkAdmin(admin.ModelAdmin):
    """
    Standalone admin for evidence-to-taxon identification links.

    This is useful for checking possible identifications across all evidence.
    """

    list_display = (
        "evidence_item",
        "taxon",
        "identification_status",
        "confidence_level",
        "identified_by",
        "identified_at",
    )

    list_filter = (
        "identification_status",
        "confidence_level",
    )

    search_fields = (
        "evidence_item__code",
        "taxon__code",
        "taxon__slug",
        "taxon__canonical_display_name_bs",
        "taxon__canonical_display_name_en",
        "taxon__scientific_name_current",
        "notes",
    )

    autocomplete_fields = (
        "evidence_item",
        "taxon",
        "identified_by",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )