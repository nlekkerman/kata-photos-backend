from django.conf import settings
from django.db import models


class ObservationRevision(models.Model):
    """
    Historical scientific correction/change record for an Observation.

    MVP purpose:
    - Preserve important changes to observation status, verification status,
      taxon interpretation, visibility, sensitivity, or scientific meaning.
    - Avoid silent overwrites of scientific records.
    - Keep a reviewable trail before full service/audit workflow exists.

    Important architecture rule:
    Observation is the current scientific truth record.
    ObservationRevision preserves how that truth changed over time.

    Left for later:
    - Automatic revision creation through observation services.
    - Full before/after JSON snapshots.
    - Audit integration for sensitive or permission-protected changes.
    - Revision comparison UI/API.
    """

    class RevisionType(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        VERIFICATION_CHANGED = "verification_changed", "Verification changed"
        TAXON_CHANGED = "taxon_changed", "Taxon changed"
        EVIDENCE_CHANGED = "evidence_changed", "Evidence changed"
        VISIBILITY_CHANGED = "visibility_changed", "Visibility changed"
        SENSITIVITY_CHANGED = "sensitivity_changed", "Sensitivity changed"
        NOTES_CHANGED = "notes_changed", "Notes changed"
        SCIENTIFIC_CORRECTION = "scientific_correction", "Scientific correction"
        OTHER = "other", "Other"

    observation = models.ForeignKey(
        "observations.Observation",
        on_delete=models.CASCADE,
        related_name="revisions",
        help_text="Observation whose scientific/history record changed.",
    )

    revision_type = models.CharField(
        max_length=60,
        choices=RevisionType.choices,
        default=RevisionType.OTHER,
        db_index=True,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="observation_revisions",
        blank=True,
        null=True,
        help_text="User who made or recorded this revision.",
    )

    reason = models.TextField(
        blank=True,
        help_text="Human explanation for why this revision was made.",
    )

    previous_observation_status = models.CharField(
        max_length=60,
        blank=True,
        help_text="Previous observation status before this revision.",
    )

    new_observation_status = models.CharField(
        max_length=60,
        blank=True,
        help_text="New observation status after this revision.",
    )

    previous_verification_status = models.CharField(
        max_length=60,
        blank=True,
        help_text="Previous verification status before this revision.",
    )

    new_verification_status = models.CharField(
        max_length=60,
        blank=True,
        help_text="New verification status after this revision.",
    )

    previous_taxon_summary = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short summary of previous taxon interpretation.",
    )

    new_taxon_summary = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short summary of new taxon interpretation.",
    )

    previous_visibility_level = models.CharField(
        max_length=60,
        blank=True,
        help_text="Previous visibility level before this revision.",
    )

    new_visibility_level = models.CharField(
        max_length=60,
        blank=True,
        help_text="New visibility level after this revision.",
    )

    previous_sensitivity_level = models.CharField(
        max_length=60,
        blank=True,
        help_text="Previous sensitivity level before this revision.",
    )

    new_sensitivity_level = models.CharField(
        max_length=60,
        blank=True,
        help_text="New sensitivity level after this revision.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Internal revision notes. Do not expose publicly later.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["observation", "revision_type"]),
            models.Index(fields=["revision_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.observation.code} - {self.get_revision_type_display()}"