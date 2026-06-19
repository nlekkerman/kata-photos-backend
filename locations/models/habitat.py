import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Habitat(models.Model):
    """
    Canonical habitat classification for Kata Wild.

    MVP purpose:
    - Store habitat vocabulary such as forest, river, wetland, meadow, canyon, or mixed habitat.
    - Keep habitat context reusable across monitoring points and future observations.
    - Avoid loose frontend-only habitat labels.

    Important architecture rule:
    Habitat describes ecological context.
    Habitat changes over time will later belong to HabitatChangeRecord, not random text fields.

    Left for later:
    - Habitat relationship/history support.
    - HabitatChangeRecord.
    - Public-safe habitat selectors.
    """

    class HabitatType(models.TextChoices):
        FOREST = "forest", "Forest"
        RIVER = "river", "River"
        WETLAND = "wetland", "Wetland"
        MOUNTAIN = "mountain", "Mountain"
        GRASSLAND = "grassland", "Grassland"
        ROCKY_TERRAIN = "rocky_terrain", "Rocky terrain"
        MEADOW = "meadow", "Meadow"
        CANYON = "canyon", "Canyon"
        HUMAN_ADJACENT = "human_adjacent", "Human adjacent"
        MIXED = "mixed", "Mixed"
        UNKNOWN = "unknown", "Unknown"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    code = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    parent_habitat = models.ForeignKey(
        "locations.Habitat",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="child_habitats",
    )

    name_bs = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180, blank=True)

    habitat_type = models.CharField(
        max_length=40,
        choices=HabitatType.choices,
        default=HabitatType.UNKNOWN,
    )

    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Habitat"
        verbose_name_plural = "Habitats"
        ordering = ["name_bs"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["habitat_type"]),
            models.Index(fields=["is_published"]),
        ]

    def clean(self):
        """
        Validate habitat hierarchy consistency.

        MVP purpose:
        - Prevent a habitat from becoming its own parent.
        - Prevent simple parent-chain cycles that break hierarchy traversal.
        - Keep Habitat as canonical ecological vocabulary, not loose frontend text.

        Architecture rule:
        - Habitat describes ecological context.
        - Habitat hierarchy must remain acyclic.
        - Habitat changes over time belong to future HabitatChangeRecord, not random text fields.

        Left for later:
        - Dedicated habitat hierarchy service.
        - HabitatChangeRecord.
        - Public-safe habitat selectors.
        """

        super().clean()

        errors = {}

        if self.pk and self.parent_habitat_id == self.pk:
            errors["parent_habitat"] = "A habitat cannot be its own parent."

        current_parent = self.parent_habitat
        visited_ids = set()

        while current_parent:
            if current_parent.pk in visited_ids:
                errors["parent_habitat"] = (
                    "Habitat parent chain contains a cycle."
                )
                break

            visited_ids.add(current_parent.pk)

            if self.pk and current_parent.pk == self.pk:
                errors["parent_habitat"] = (
                    "Habitat parent chain cannot contain this habitat."
                )
                break

            current_parent = current_parent.parent_habitat

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name_bs