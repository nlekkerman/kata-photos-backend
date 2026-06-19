from django.conf import settings
from django.core.exceptions import ValidationError
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

    def clean(self):
        """
        Validate human review decision consistency.

        MVP purpose:
        - Keep review records meaningful and accountable.
        - Prevent final review decisions from being saved without reviewer/time.
        - Preserve the human-review trail that supports Observation truth.

        Architecture rule:
        - Observation is the current scientific truth record.
        - ObservationReview records human review decisions around that truth.
        - Final human decisions must identify who made the decision and when.

        Left for later:
        - Multi-reviewer workflow.
        - Dedicated review services for every review transition.
        - More detailed audit integration for sensitive review actions.
        """

        super().clean()

        errors = {}

        final_review_statuses = {
            self.ReviewStatus.VERIFIED,
            self.ReviewStatus.REJECTED,
            self.ReviewStatus.NEEDS_MORE_EVIDENCE,
            self.ReviewStatus.UNCERTAIN,
        }

        if self.review_status in final_review_statuses and not self.reviewed_by_id:
            errors["reviewed_by"] = (
                "A final review decision requires a reviewer."
            )

        if self.review_status in final_review_statuses and not self.reviewed_at:
            errors["reviewed_at"] = (
                "A final review decision requires reviewed_at."
            )

        if self.reviewed_by_id and not self.reviewed_at:
            errors["reviewed_at"] = (
                "reviewed_at is required when reviewed_by is set."
            )

        if self.reviewed_at and not self.reviewed_by_id:
            errors["reviewed_by"] = (
                "reviewed_by is required when reviewed_at is set."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.observation.code} - {self.get_review_status_display()}"