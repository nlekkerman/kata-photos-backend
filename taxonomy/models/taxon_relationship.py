import uuid

from django.db import models


class TaxonRelationship(models.Model):
    """
    Canonical ecological relationship between two taxa.

    MVP purpose:
    - Store general biological/ecological relationships such as predator/prey,
      pollination, symbiosis, host/parasite, association, or competition.
    - Prepare future ecosystem graph support without mixing it into observations.

    Important architecture rule:
    TaxonRelationship describes general taxon-to-taxon relationships.
    Specific real-world observed events belong later to ObservationRelationship or ObservationEvent.

    Left for later:
    - Cycle/duplicate inverse relationship validation.
    - Evidence-backed relationship review workflow.
    - Public-safe selectors for sensitive ecological relationships.
    """

    class RelationshipType(models.TextChoices):
        PREDATOR_OF = "predator_of", "Predator of"
        PREY_OF = "prey_of", "Prey of"
        POLLINATES = "pollinates", "Pollinates"
        POLLINATED_BY = "pollinated_by", "Pollinated by"
        HOST_OF = "host_of", "Host of"
        PARASITE_OF = "parasite_of", "Parasite of"
        SYMBIOTIC_WITH = "symbiotic_with", "Symbiotic with"
        ASSOCIATED_WITH = "associated_with", "Associated with"
        COMPETES_WITH = "competes_with", "Competes with"
        FEEDS_ON = "feeds_on", "Feeds on"
        DEPENDS_ON = "depends_on", "Depends on"
        SUPPORTS_HABITAT_FOR = "supports_habitat_for", "Supports habitat for"
        DISPERSES_SEEDS_FOR = "disperses_seeds_for", "Disperses seeds for"
        OTHER = "other", "Other"

    class ConfidenceLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        VERIFIED = "verified", "Verified"
        UNKNOWN = "unknown", "Unknown"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    source_taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.CASCADE,
        related_name="outgoing_taxon_relationships",
    )
    target_taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.CASCADE,
        related_name="incoming_taxon_relationships",
    )

    relationship_type = models.CharField(
        max_length=60,
        choices=RelationshipType.choices,
        default=RelationshipType.OTHER,
    )

    confidence_level = models.CharField(
        max_length=30,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.UNKNOWN,
    )

    source = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Taxon relationship"
        verbose_name_plural = "Taxon relationships"
        ordering = [
            "source_taxon__canonical_display_name_bs",
            "relationship_type",
            "target_taxon__canonical_display_name_bs",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_taxon", "target_taxon", "relationship_type"],
                name="unique_taxon_relationship_type",
            ),
        ]
        indexes = [
            models.Index(fields=["relationship_type"]),
            models.Index(fields=["confidence_level"]),
        ]

    def __str__(self):
        return (
            f"{self.source_taxon} "
            f"{self.get_relationship_type_display()} "
            f"{self.target_taxon}"
        )