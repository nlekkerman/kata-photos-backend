from django.db.models import QuerySet

from evidence.models.evidence_item import EvidenceItem


def get_public_evidence_items() -> QuerySet[EvidenceItem]:
    """
    Return evidence items that are safe for public display.

    MVP purpose:
    - Give future public APIs one canonical place to read public evidence.
    - Exclude private, internal, restricted, sensitive, rejected, draft, and archived evidence.
    - Prevent public views from accidentally exposing protected scientific evidence context.

    Architecture rule:
    - Evidence supports Observation truth but does not replace Observation truth.
    - Public APIs must not decide evidence safety inline.
    - Protected evidence context, private notes, exact monitoring context, and restricted
      scientific metadata must stay out of public selectors.

    Left for later:
    - Public-safe evidence file selector.
    - Workspace/research evidence selectors with scoped RBAC and audit.
    - Redaction rules for sensitive species, locations, and monitoring points.
    """

    return (
        EvidenceItem.objects.filter(
            visibility_level=EvidenceItem.VisibilityLevel.PUBLIC_SAFE,
            sensitivity_level=EvidenceItem.SensitivityLevel.NORMAL,
            status=EvidenceItem.Status.VERIFIED,
        )
        .select_related(
            "project",
            "monitoring_point",
            "camera_deployment",
            "created_by",
        )
        .order_by("-recorded_at", "-capture_started_at", "-created_at")
    )


def get_public_evidence_item_by_code(code: str) -> EvidenceItem | None:
    """
    Return one public-safe evidence item by stable evidence code.

    MVP purpose:
    - Give future public detail APIs a safe lookup helper.
    - Return None instead of leaking private, sensitive, rejected, or unpublished evidence.

    Architecture rule:
    - Public evidence lookup must use the same safety rules as public evidence lists.
    """

    return get_public_evidence_items().filter(code=code).first()