from django.db import models
from django.db.models import Q


class ObservationEvidenceLink(models.Model):
    """
    Link between a canonical Observation and supporting EvidenceItem.

    MVP purpose:
    - Allow one observation to be supported by one or more evidence records.
    - Allow one evidence item to support multiple observations later.
    - Preserve how evidence supports the scientific truth record.

    Important architecture rule:
    This link does not make Evidence the truth.
    Observation remains the scientific truth record.

    Left for later:
    - Evidence quality review workflow.
    - Link/unlink service with audit logging.
    - Policy checks for restricted evidence.
    """

    class LinkType(models.TextChoices):
        PRIMARY = "primary", "Primary evidence"
        SUPPORTING = "supporting", "Supporting evidence"
        CONTEXT = "context", "Context evidence"
        DISPUTED = "disputed", "Disputed evidence"

    observation = models.ForeignKey(
        "observations.Observation",
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )

    evidence_item = models.ForeignKey(
        "evidence.EvidenceItem",
        on_delete=models.PROTECT,
        related_name="observation_links",
    )

    link_type = models.CharField(
        max_length=40,
        choices=LinkType.choices,
        default=LinkType.SUPPORTING,
        db_index=True,
    )

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marks the main evidence item for this observation.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional internal note explaining how this evidence supports the observation.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "link_type", "evidence_item_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["observation", "evidence_item"],
                name="unique_observation_evidence_link",
            ),
            models.UniqueConstraint(
                fields=["observation"],
                condition=Q(is_primary=True),
                name="unique_primary_evidence_per_observation",
            ),
        ]

    def __str__(self):
        return f"{self.observation.code} -> {self.evidence_item.code}"