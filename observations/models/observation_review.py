from django.conf import settings
from django.db import models


class ObservationReview(models.Model):
    """
    Manual review trail for an Observation.

    MVP purpose:
    - Record human review decisions around observation quality, identification,
      verification, rejection, or review needs.
    - Keep review notes separate from the main Observation fields.

    Important architecture rule:
    Human review supports scientific trust.
    Later, verification changes should go through services and audit logging.

    Left for later:
    - Full observation revision model.
    - Review service.
    - Audit integration.
    - Multi-reviewer workflow.
    """

    class ReviewStatus(models.TextChoices):
        REVIEW_NEEDED = "review_needed", "Review needed"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        NEEDS_MORE_EVIDENCE = "needs_more_evidence", "Needs more evidence"
        UNCERTAIN = "uncertain", "Uncertain"

    observation = models.ForeignKey(
        "observations.Observation",
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="observation_reviews",
        blank=True,
        null=True,
    )

    review_status = models.CharField(
        max_length=40,
        choices=ReviewStatus.choices,
        default=ReviewStatus.REVIEW_NEEDED,
        db_index=True,
    )

    review_notes = models.TextField(
        blank=True,
        help_text="Internal review notes. Do not expose publicly later.",
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when this review decision was made.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reviewed_at", "-created_at"]
        indexes = [
            models.Index(fields=["review_status", "reviewed_at"]),
        ]

    def __str__(self):
        return f"{self.observation.code} - {self.get_review_status_display()}"