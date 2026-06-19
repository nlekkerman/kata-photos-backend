import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EvidenceTaxonLink(models.Model):
    """
    Possible taxon identification found in evidence.

    Important canonical rule:
    this is not final observation truth. It only says that evidence may show
    this taxon, with a recorded uncertainty/confidence level.

    MVP scope:
    - Link EvidenceItem to Taxon.
    - Preserve uncertainty and identification status.

    Left for later:
    - Expert verification workflow.
    - Multi-reviewer identification history.
    - Scientific revision/audit trail.
    """

    class IdentificationStatus(models.TextChoices):
        POSSIBLE = "possible", "Possible"
        LIKELY = "likely", "Likely"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        UNKNOWN = "unknown", "Unknown"

    class ConfidenceLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        EXPERT_CONFIRMED = "expert_confirmed", "Expert confirmed"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    evidence_item = models.ForeignKey(
        "evidence.EvidenceItem",
        on_delete=models.CASCADE,
        related_name="taxon_links",
    )

    taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.PROTECT,
        related_name="evidence_links",
    )

    identification_status = models.CharField(
        max_length=40,
        choices=IdentificationStatus.choices,
        default=IdentificationStatus.POSSIBLE,
    )

    confidence_level = models.CharField(
        max_length=40,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.MEDIUM,
    )

    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="identified_evidence_taxa",
        blank=True,
        null=True,
    )

    identified_at = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(
        blank=True,
        help_text="Notes explaining why this taxon identification was suggested.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["taxon__canonical_display_name_bs", "created_at"]
        verbose_name = "Evidence taxon link"
        verbose_name_plural = "Evidence taxon links"
        constraints = [
            models.UniqueConstraint(
                fields=["evidence_item", "taxon"],
                name="unique_taxon_per_evidence_item",
            )
        ]
        indexes = [
            models.Index(fields=["evidence_item", "identification_status"]),
            models.Index(fields=["taxon", "confidence_level"]),
        ]
        
    def clean(self):
        """
        Validate evidence-level taxon identification consistency.

        MVP purpose:
        - Keep EvidenceTaxonLink accountable when a human identifies evidence.
        - Prevent expert-confirmed evidence taxon links without reviewer/time.
        - Keep rejected identifications traceable instead of anonymous.

        Architecture rule:
        - EvidenceTaxonLink is evidence interpretation, not final Observation truth.
        - Human-confirmed or rejected evidence identification must record who made
          the decision and when.
        - Final truth is still created through Observation review/verification.

        Left for later:
        - Multi-reviewer evidence identification workflow.
        - AI suggestion comparison and confidence scoring.
        - Audit logging for sensitive evidence-identification changes.
        """

        super().clean()

        errors = {}

        human_decision_statuses = {
            self.IdentificationStatus.CONFIRMED,
            self.IdentificationStatus.REJECTED,
        }

        human_decision_confidence_levels = {
            self.ConfidenceLevel.EXPERT_CONFIRMED,
        }

        requires_human_decision = (
            self.identification_status in human_decision_statuses
            or self.confidence_level in human_decision_confidence_levels
        )

        if requires_human_decision and not self.identified_by_id:
            errors["identified_by"] = (
                "Confirmed, rejected, or expert-confirmed evidence taxon links require identified_by."
            )

        if requires_human_decision and not self.identified_at:
            errors["identified_at"] = (
                "Confirmed, rejected, or expert-confirmed evidence taxon links require identified_at."
            )

        if self.identified_by_id and not self.identified_at:
            errors["identified_at"] = (
                "identified_at is required when identified_by is set."
            )

        if self.identified_at and not self.identified_by_id:
            errors["identified_by"] = (
                "identified_by is required when identified_at is set."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.evidence_item.code} - {self.taxon}"