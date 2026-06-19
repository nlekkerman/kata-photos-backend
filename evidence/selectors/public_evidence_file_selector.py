from django.db.models import QuerySet

from evidence.models.evidence_file import EvidenceFile
from evidence.selectors.public_evidence_selector import get_public_evidence_items


def get_public_evidence_files() -> QuerySet[EvidenceFile]:
    """
    Return evidence files that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public evidence files.
    - Only expose files attached to public-safe verified evidence items.
    - Prevent public views from accidentally exposing private/restricted storage objects.

    Architecture rule:
    - EvidenceFile stores media/file storage metadata.
    - EvidenceItem decides public evidence eligibility.
    - Public APIs must not expose protected files unless the parent evidence item
      is already public-safe through the canonical public evidence selector.

    Left for later:
    - Public thumbnail/preview-only selector.
    - Signed URL generation service.
    - Workspace/research file selectors with scoped RBAC and audit.
    """

    return (
        EvidenceFile.objects.filter(
            evidence_item__in=get_public_evidence_items(),
            is_primary=True,
        )
        .select_related("evidence_item")
        .order_by("evidence_item__code", "-is_primary", "created_at")
    )


def get_public_evidence_files_for_item(evidence_item_code: str) -> QuerySet[EvidenceFile]:
    """
    Return public-safe files for one public-safe evidence item.

    MVP purpose:
    - Give future evidence detail APIs a safe file lookup helper.
    - Return no files if the parent evidence item is not public-safe.

    Architecture rule:
    - File access inherits public safety from the parent EvidenceItem selector.
    """

    return get_public_evidence_files().filter(evidence_item__code=evidence_item_code)


def get_primary_public_evidence_file(evidence_item_code: str) -> EvidenceFile | None:
    """
    Return the primary public-safe file for one public-safe evidence item.

    MVP purpose:
    - Give future public cards/detail APIs one safe primary media file.
    - Return None instead of leaking files from private or sensitive evidence.

    Architecture rule:
    - Public primary-file lookup must use the same safety rules as public evidence files.
    """

    return get_public_evidence_files_for_item(evidence_item_code).first()