from django.contrib import admin

from taxonomy.models import (
    ConservationStatus,
    Taxon,
    TaxonCharacteristic,
    TaxonName,
    TaxonRelationship,
)


class TaxonNameInline(admin.TabularInline):
    """
    Inline naming records for a Taxon.

    MVP purpose:
    - Add common, scientific, local, synonym, or historical names directly from the Taxon screen.
    - Keep names separate from biological identity, because Taxon.code remains the stable identity anchor.

    Left for later:
    - Validation that only one primary name exists per taxon/name type/language.
    - Source-quality review if taxonomy becomes research-grade.
    """

    model = TaxonName
    extra = 0
    fields = (
        "name",
        "name_type",
        "language_code",
        "is_primary",
        "source",
    )


class ConservationStatusInline(admin.TabularInline):
    """
    Inline conservation status records for a Taxon.

    MVP purpose:
    - Attach conservation, legal, local, or project-specific status from the Taxon screen.
    - Keep conservation status separate from Taxon identity.

    Left for later:
    - Source document links.
    - Status review workflow.
    - Policy rules for sensitive conservation categories.
    """

    model = ConservationStatus
    extra = 0
    fields = (
        "status_type",
        "status_value",
        "jurisdiction",
        "source",
        "valid_from",
        "valid_to",
    )

class TaxonCharacteristicInline(admin.TabularInline):
    """
    Inline biological/ecological characteristics for a Taxon.

    MVP purpose:
    - Allow basic taxon facts to be added from the Taxon screen.
    - Keep general taxon facts separate from observation-specific behavior.
    """

    model = TaxonCharacteristic
    extra = 0
    fields = (
        "characteristic_type",
        "value_text_bs",
        "value_text_en",
        "value_number",
        "unit",
        "confidence_level",
        "visibility_level",
    )


class OutgoingTaxonRelationshipInline(admin.TabularInline):
    """
    Inline outgoing ecological relationships from this Taxon to another Taxon.

    MVP purpose:
    - Show simple source_taxon -> target_taxon relationships from the Taxon screen.
    - Keep general ecological relationships separate from specific observation events.
    """

    model = TaxonRelationship
    fk_name = "source_taxon"
    extra = 0
    fields = (
        "target_taxon",
        "relationship_type",
        "confidence_level",
        "source",
    )
    autocomplete_fields = (
        "target_taxon",
    )

@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    """
    Django admin management for canonical Taxon records.

    MVP purpose:
    - Support manual creation of animals, plants, fungi, unknown taxa, and future biological groups.
    - Keep biological identity separate from names, tags, media, galleries, and observations.

    Important:
    Public exposure and sensitive-taxon handling will later be enforced through selectors,
    policies, visibility, sensitivity, and audit where required.
    """

    list_display = (
        "canonical_display_name_bs",
        "code",
        "taxon_group",
        "taxon_rank",
        "scientific_name_current",
        "is_sensitive",
        "is_published",
    )
    list_filter = (
        "taxon_group",
        "taxon_rank",
        "native_status",
        "sensitivity_level",
        "is_sensitive",
        "is_published",
    )
    search_fields = (
        "canonical_display_name_bs",
        "canonical_display_name_en",
        "scientific_name_current",
        "code",
        "slug",
    )
    autocomplete_fields = (
        "parent_taxon",
    )
    prepopulated_fields = {
        "slug": ("canonical_display_name_bs",),
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
                    "parent_taxon",
                )
            },
        ),
        (
            "Taxonomy",
            {
                "fields": (
                    "taxon_rank",
                    "taxon_group",
                    "scientific_name_current",
                    "native_status",
                )
            },
        ),
        (
            "Display names",
            {
                "fields": (
                    "canonical_display_name_bs",
                    "canonical_display_name_en",
                )
            },
        ),
        (
            "Descriptions and identification notes",
            {
                "fields": (
                    "description_bs",
                    "description_en",
                    "identification_notes_bs",
                    "identification_notes_en",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Sensitivity and publication",
            {
                "fields": (
                    "sensitivity_level",
                    "is_sensitive",
                    "is_published",
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
    inlines = [
        TaxonNameInline,
        ConservationStatusInline,
        TaxonCharacteristicInline,
        OutgoingTaxonRelationshipInline,
    ]


@admin.register(TaxonName)
class TaxonNameAdmin(admin.ModelAdmin):
    """
    Django admin management for TaxonName records.

    MVP purpose:
    - Review and edit multilingual, local, scientific, synonym, and historical names.
    - Preserve the locked rule that names are labels, not identity.
    """

    list_display = (
        "name",
        "taxon",
        "name_type",
        "language_code",
        "is_primary",
    )
    list_filter = (
        "name_type",
        "language_code",
        "is_primary",
    )
    search_fields = (
        "name",
        "taxon__canonical_display_name_bs",
        "taxon__canonical_display_name_en",
        "taxon__scientific_name_current",
        "taxon__code",
    )
    autocomplete_fields = (
        "taxon",
    )
    list_select_related = (
        "taxon",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Name",
            {
                "fields": (
                    "uuid",
                    "taxon",
                    "name",
                    "name_type",
                    "language_code",
                    "is_primary",
                )
            },
        ),
        (
            "Source and history",
            {
                "fields": (
                    "source",
                    "valid_from",
                    "valid_to",
                    "notes",
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


@admin.register(ConservationStatus)
class ConservationStatusAdmin(admin.ModelAdmin):
    """
    Django admin management for ConservationStatus records.

    MVP purpose:
    - Track conservation, legal, regional, local, and project-specific status for taxa.
    - Keep status history ready for future scientific and public-safe decisions.
    """

    list_display = (
        "taxon",
        "status_type",
        "status_value",
        "jurisdiction",
        "valid_from",
        "valid_to",
    )
    list_filter = (
        "status_type",
        "status_value",
        "jurisdiction",
    )
    search_fields = (
        "taxon__canonical_display_name_bs",
        "taxon__canonical_display_name_en",
        "taxon__scientific_name_current",
        "taxon__code",
        "jurisdiction",
        "source",
    )
    autocomplete_fields = (
        "taxon",
    )
    list_select_related = (
        "taxon",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Conservation status",
            {
                "fields": (
                    "uuid",
                    "taxon",
                    "status_type",
                    "status_value",
                    "jurisdiction",
                )
            },
        ),
        (
            "Source and validity",
            {
                "fields": (
                    "source",
                    "valid_from",
                    "valid_to",
                    "notes",
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

@admin.register(TaxonCharacteristic)
class TaxonCharacteristicAdmin(admin.ModelAdmin):
    """
    Django admin management for TaxonCharacteristic records.

    MVP purpose:
    - Manage general biological and ecological facts for taxa.
    - Avoid storing taxon facts as loose notes, tags, or frontend-only labels.
    """

    list_display = (
        "taxon",
        "characteristic_type",
        "confidence_level",
        "visibility_level",
        "unit",
    )
    list_filter = (
        "characteristic_type",
        "confidence_level",
        "visibility_level",
    )
    search_fields = (
        "taxon__canonical_display_name_bs",
        "taxon__canonical_display_name_en",
        "taxon__scientific_name_current",
        "taxon__code",
        "value_text_bs",
        "value_text_en",
        "source",
    )
    autocomplete_fields = (
        "taxon",
    )
    list_select_related = (
        "taxon",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )


@admin.register(TaxonRelationship)
class TaxonRelationshipAdmin(admin.ModelAdmin):
    """
    Django admin management for TaxonRelationship records.

    MVP purpose:
    - Manage general ecological relationships between taxa.
    - Keep ecosystem relationships separate from specific observed events.
    """

    list_display = (
        "source_taxon",
        "relationship_type",
        "target_taxon",
        "confidence_level",
    )
    list_filter = (
        "relationship_type",
        "confidence_level",
    )
    search_fields = (
        "source_taxon__canonical_display_name_bs",
        "source_taxon__canonical_display_name_en",
        "source_taxon__scientific_name_current",
        "source_taxon__code",
        "target_taxon__canonical_display_name_bs",
        "target_taxon__canonical_display_name_en",
        "target_taxon__scientific_name_current",
        "target_taxon__code",
        "source",
        "notes",
    )
    autocomplete_fields = (
        "source_taxon",
        "target_taxon",
    )
    list_select_related = (
        "source_taxon",
        "target_taxon",
    )
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )