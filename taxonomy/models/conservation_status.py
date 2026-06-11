import uuid

from django.db import models


class ConservationStatus(models.Model):
    """
    Conservation status record for a Taxon.

    MVP purpose:
    - Track global, national, regional, legal, local, or project-specific status.
    - Preserve conservation context without hardcoding it into Taxon fields.

    Important architecture rule:
    Conservation status supports scientific and public-safe decisions,
    but access to sensitive taxa still belongs to policies/selectors later.

    Left for later:
    - Source document attachments.
    - Status history review workflow.
    - Policy rules for sensitive conservation categories.
    """

    class StatusType(models.TextChoices):
        GLOBAL = "global", "Global"
        LOCAL = "local", "Local"
        NATIONAL = "national", "National"
        REGIONAL = "regional", "Regional"
        LEGAL = "legal", "Legal"
        PROJECT_SPECIFIC = "project_specific", "Project specific"

    class StatusValue(models.TextChoices):
        LEAST_CONCERN = "least_concern", "Least concern"
        NEAR_THREATENED = "near_threatened", "Near threatened"
        VULNERABLE = "vulnerable", "Vulnerable"
        ENDANGERED = "endangered", "Endangered"
        CRITICALLY_ENDANGERED = "critically_endangered", "Critically endangered"
        EXTINCT_IN_WILD = "extinct_in_wild", "Extinct in wild"
        EXTINCT = "extinct", "Extinct"
        DATA_DEFICIENT = "data_deficient", "Data deficient"
        NOT_EVALUATED = "not_evaluated", "Not evaluated"
        PROTECTED = "protected", "Protected"
        STRICTLY_PROTECTED = "strictly_protected", "Strictly protected"
        HUNTING_ALLOWED = "hunting_allowed", "Hunting allowed"
        SEASONAL_PROTECTION = "seasonal_protection", "Seasonal protection"
        CONSERVATION_PRIORITY = "conservation_priority", "Conservation priority"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.CASCADE,
        related_name="conservation_statuses",
    )

    status_type = models.CharField(
        max_length=40,
        choices=StatusType.choices,
        default=StatusType.LOCAL,
    )
    status_value = models.CharField(
        max_length=50,
        choices=StatusValue.choices,
        default=StatusValue.NOT_EVALUATED,
    )

    jurisdiction = models.CharField(max_length=180, blank=True)
    source = models.CharField(max_length=255, blank=True)

    valid_from = models.DateField(blank=True, null=True)
    valid_to = models.DateField(blank=True, null=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["taxon__canonical_display_name_bs", "status_type", "status_value"]
        indexes = [
            models.Index(fields=["status_type"]),
            models.Index(fields=["status_value"]),
            models.Index(fields=["jurisdiction"]),
        ]

    def __str__(self):
        return f"{self.taxon} - {self.get_status_value_display()}"