import uuid

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

    def __str__(self):
        return self.name_bs