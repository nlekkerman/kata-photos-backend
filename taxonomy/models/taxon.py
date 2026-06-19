import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Taxon(models.Model):
    """
    Canonical biological identity record for Kata Wild.

    MVP purpose:
    - Store animals, plants, fungi, mushrooms, insects, trees, flowers, unknown taxa,
      and future biological groups in one canonical model.
    - Avoid species-only architecture.
    - Allow incomplete identification without losing scientific value.

    Important architecture rule:
    Taxon is biological identity truth.
    It is not a tag, gallery category, frontend label, or media caption.

    Left for later:
    - Taxon relationship graph.
    - Taxon characteristics.
    - Sensitive taxon access policies.
    - Scientific review workflow for taxonomic corrections.
    """

    class TaxonRank(models.TextChoices):
        KINGDOM = "kingdom", "Kingdom"
        PHYLUM = "phylum", "Phylum"
        CLASS = "class", "Class"
        ORDER = "order", "Order"
        FAMILY = "family", "Family"
        GENUS = "genus", "Genus"
        SPECIES = "species", "Species"
        SUBSPECIES = "subspecies", "Subspecies"
        GROUP = "group", "Group"
        UNKNOWN = "unknown", "Unknown"

    class TaxonGroup(models.TextChoices):
        ANIMAL = "animal", "Animal"
        MAMMAL = "mammal", "Mammal"
        BIRD = "bird", "Bird"
        REPTILE = "reptile", "Reptile"
        AMPHIBIAN = "amphibian", "Amphibian"
        INSECT = "insect", "Insect"
        PLANT = "plant", "Plant"
        TREE = "tree", "Tree"
        FLOWER = "flower", "Flower"
        FUNGUS = "fungus", "Fungus"
        MUSHROOM = "mushroom", "Mushroom"
        MOSS = "moss", "Moss"
        LICHEN = "lichen", "Lichen"
        OTHER = "other", "Other"
        UNKNOWN = "unknown", "Unknown"

    class NativeStatus(models.TextChoices):
        NATIVE = "native", "Native"
        INTRODUCED = "introduced", "Introduced"
        INVASIVE = "invasive", "Invasive"
        REINTRODUCED = "reintroduced", "Reintroduced"
        UNCERTAIN = "uncertain", "Uncertain"
        UNKNOWN = "unknown", "Unknown"

    class SensitivityLevel(models.TextChoices):
        NORMAL = "normal", "Normal"
        SENSITIVE = "sensitive", "Sensitive"
        HIGHLY_SENSITIVE = "highly_sensitive", "Highly sensitive"
        CRITICAL = "critical", "Critical"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    parent_taxon = models.ForeignKey(
        "taxonomy.Taxon",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="child_taxa",
    )

    taxon_rank = models.CharField(
        max_length=30,
        choices=TaxonRank.choices,
        default=TaxonRank.UNKNOWN,
    )
    taxon_group = models.CharField(
        max_length=30,
        choices=TaxonGroup.choices,
        default=TaxonGroup.UNKNOWN,
    )

    scientific_name_current = models.CharField(max_length=220, blank=True)

    canonical_display_name_bs = models.CharField(max_length=220)
    canonical_display_name_en = models.CharField(max_length=220, blank=True)

    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    identification_notes_bs = models.TextField(blank=True)
    identification_notes_en = models.TextField(blank=True)

    native_status = models.CharField(
        max_length=30,
        choices=NativeStatus.choices,
        default=NativeStatus.UNKNOWN,
    )

    sensitivity_level = models.CharField(
        max_length=30,
        choices=SensitivityLevel.choices,
        default=SensitivityLevel.NORMAL,
    )
    is_sensitive = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Taxa"
        ordering = ["canonical_display_name_bs"]
        
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["taxon_group", "taxon_rank"]),
            models.Index(fields=["is_sensitive"]),
            models.Index(fields=["is_published"]),
        ]

    def clean(self):
        """
        Validate taxon hierarchy and sensitivity consistency.

        MVP purpose:
        - Prevent circular biological hierarchy records.
        - Keep sensitive-taxon flags aligned for future selectors and policies.
        - Preserve Taxon as canonical biological identity truth.

        Architecture rule:
        - Taxon is biological identity truth, not a gallery tag or frontend label.
        - Taxon hierarchy must be acyclic.
        - Sensitive taxa must be consistently marked before public/workspace APIs use them.

        Left for later:
        - Dedicated taxonomy correction/revision workflow.
        - Rank-order validation for strict taxonomy hierarchy.
        - Sensitive taxon access policy and public-safe selectors.
        """

        super().clean()

        errors = {}

        if self.pk and self.parent_taxon_id == self.pk:
            errors["parent_taxon"] = "A taxon cannot be its own parent."

        current_parent = self.parent_taxon
        visited_ids = set()

        while current_parent:
            if current_parent.pk in visited_ids:
                errors["parent_taxon"] = (
                    "Taxon parent chain contains a cycle."
                )
                break

            visited_ids.add(current_parent.pk)

            if self.pk and current_parent.pk == self.pk:
                errors["parent_taxon"] = (
                    "Taxon parent chain cannot contain this taxon."
                )
                break

            current_parent = current_parent.parent_taxon

        if self.sensitivity_level == self.SensitivityLevel.NORMAL and self.is_sensitive:
            errors["is_sensitive"] = (
                "Taxa with normal sensitivity level must not be marked sensitive."
            )

        if self.sensitivity_level != self.SensitivityLevel.NORMAL and not self.is_sensitive:
            errors["is_sensitive"] = (
                "Taxa with sensitive, highly sensitive, or critical sensitivity level must be marked sensitive."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.canonical_display_name_bs