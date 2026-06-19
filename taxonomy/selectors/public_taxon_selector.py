from django.db.models import QuerySet

from taxonomy.models.taxon import Taxon


def get_public_taxa() -> QuerySet[Taxon]:
    """
    Return taxa that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public taxonomy data.
    - Exclude unpublished taxa.
    - Exclude sensitive taxa until public-safe redaction rules exist.

    Architecture rule:
    - Taxon is canonical biological identity truth.
    - Public APIs must not decide safety inline.
    - Public-safe filtering belongs in selectors, not views or frontend code.

    Left for later:
    - Public redaction for sensitive taxa.
    - Region/project-specific public taxon filtering.
    - Conservation-status summary selection.
    """

    return (
        Taxon.objects.filter(
            is_published=True,
            is_sensitive=False,
            sensitivity_level=Taxon.SensitivityLevel.NORMAL,
        )
        .select_related("parent_taxon")
        .order_by("canonical_display_name_bs")
    )


def get_public_taxon_by_slug(slug: str) -> Taxon | None:
    """
    Return one public-safe taxon by slug.

    MVP purpose:
    - Give future detail APIs a safe lookup helper.
    - Return None instead of leaking unpublished or sensitive taxa.

    Architecture rule:
    - Public taxon lookup must use the same safety rules as public taxon lists.
    """

    return get_public_taxa().filter(slug=slug).first()