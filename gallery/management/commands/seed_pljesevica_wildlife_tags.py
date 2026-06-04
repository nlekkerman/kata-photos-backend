"""
Management command: seed_pljesevica_wildlife_tags

Creates an initial curated set of Plješevica / Una / Dinaric wildlife tags.

Safe to run multiple times:
  - Tags that already exist by slug are skipped.
  - Existing tags are never overwritten.
  - No tags are ever deleted.

Usage:
    python manage.py seed_pljesevica_wildlife_tags
    python manage.py seed_pljesevica_wildlife_tags --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from gallery.models import Tag

# ---------------------------------------------------------------------------
# Seed data: (name_bs, name_en)
# Slugs are computed from name_bs via django.utils.text.slugify, matching
# the behaviour of Tag.save().  The command deduplicates by computed slug
# before writing, so running it twice is always safe.
# ---------------------------------------------------------------------------

SEED_TAGS = [
    # ---- Broad animal groups ------------------------------------------------
    ("Sisari", "Mammals"),
    ("Ptice", "Birds"),
    ("Grabljivice", "Raptors"),
    ("Sove", "Owls"),
    ("Vodene ptice", "Water birds"),
    ("Gmizavci", "Reptiles"),
    ("Vodozemci", "Amphibians"),
    ("Ribe", "Fish"),
    ("Insekti", "Insects"),
    ("Leptiri", "Butterflies"),
    ("Šumske životinje", "Forest animals"),
    ("Noćne životinje", "Nocturnal animals"),
    ("Tragovi životinja", "Animal tracks"),
    # ---- Large mammals / iconic regional wildlife ---------------------------
    ("Smeđi medvjed", "Brown bear"),
    ("Vuk", "Wolf"),
    ("Ris", "Eurasian lynx"),
    ("Lisica", "Red fox"),
    ("Divlja mačka", "Wildcat"),
    ("Jazavac", "Badger"),
    ("Kuna", "Marten"),
    ("Vidra", "Otter"),
    ("Divlja svinja", "Wild boar"),
    ("Srna", "Roe deer"),
    ("Jelen", "Red deer"),
    ("Divokoza", "Chamois"),
    ("Zec", "Hare"),
    ("Vjeverica", "Squirrel"),
    ("Jež", "Hedgehog"),
    ("Šišmiši", "Bats"),
    # ---- Birds and bird groups ----------------------------------------------
    ("Orao", "Eagle"),
    ("Sokol", "Falcon"),
    ("Jastreb", "Hawk"),
    ("Mišar", "Buzzard"),
    ("Kobac", "Sparrowhawk"),
    ("Sova", "Owl"),
    ("Ćuk", "Little owl"),
    ("Djetlić", "Woodpecker"),
    ("Vrana", "Crow"),
    ("Gavran", "Raven"),
    ("Svraka", "Magpie"),
    ("Sjenica", "Tit"),
    ("Crvendać", "Robin"),
    ("Kos", "Blackbird"),
    ("Drozd", "Thrush"),
    ("Čaplja", "Heron"),
    ("Patka", "Duck"),
    ("Vodomar", "Kingfisher"),
    # ---- Reptiles and amphibians --------------------------------------------
    ("Zmije", "Snakes"),
    ("Poskok", "Nose-horned viper"),
    ("Bjelouška", "Grass snake"),
    ("Gušteri", "Lizards"),
    ("Zelembać", "Green lizard"),
    ("Žabe", "Frogs"),
    ("Krastače", "Toads"),
    ("Daždevnjak", "Salamander"),
    ("Crni daždevnjak", "Black salamander"),
    ("Vodenjak", "Newt"),
    # ---- River / fish wildlife ----------------------------------------------
    ("Pastrmka", "Trout"),
    ("Lipljen", "Grayling"),
    ("Mladica", "Huchen"),
    ("Klen", "Chub"),
    ("Mrena", "Barbel"),
    ("Riječne životinje", "River animals"),
    # ---- Insects / butterflies / small wildlife -----------------------------
    ("Pčele", "Bees"),
    ("Bumbari", "Bumblebees"),
    ("Vilin konjic", "Dragonfly"),
    ("Mravi", "Ants"),
    ("Skakavci", "Grasshoppers"),
    ("Bube", "Beetles"),
    ("Paukovi", "Spiders"),
    ("Puževi", "Snails"),
    # ---- Habitat / observation tags -----------------------------------------
    ("Šuma", "Forest"),
    ("Planina", "Mountain"),
    ("Livada", "Meadow"),
    ("Rijeka", "River"),
    ("Potok", "Stream"),
    ("Kanjon", "Canyon"),
    ("Pećina", "Cave"),
    ("Snijeg", "Snow"),
    ("Noćni snimci", "Night footage"),
    ("Jutarnji snimci", "Morning footage"),
    ("Hranjenje", "Feeding"),
    ("Mladunčad", "Young animals"),
    ("Migracija", "Migration"),
]


class Command(BaseCommand):
    help = (
        "Seed initial Plješevica / Una / Dinaric wildlife tags. "
        "Safe to run multiple times — existing tags are never overwritten or deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            default=False,
            help="Print what would be created/skipped without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes will be written.\n"))

        created_count = 0
        skipped_count = 0
        seen_slugs: set[str] = set()

        for name_bs, name_en in SEED_TAGS:
            # Django's slugify drops 'đ' entirely; transliterate it to 'd'
            # so "Smeđi medvjed" → "smedi-medvjed" instead of "smei-medvjed".
            slug = slugify(name_bs.replace('đ', 'd').replace('Đ', 'd'))

            # Guard against duplicate entries within the seed list itself.
            if slug in seen_slugs:
                self.stdout.write(
                    self.style.WARNING(f"  DUPLICATE in seed list — skipping: {slug} ({name_bs})")
                )
                skipped_count += 1
                continue
            seen_slugs.add(slug)

            if dry_run:
                exists = Tag.objects.filter(slug=slug).exists()
                if exists:
                    self.stdout.write(f"  [skip]   {slug}  ({name_bs})")
                    skipped_count += 1
                else:
                    self.stdout.write(f"  [create] {slug}  ({name_bs})")
                    created_count += 1
            else:
                _tag, created = Tag.objects.get_or_create(
                    slug=slug,
                    defaults={"name_bs": name_bs, "name_en": name_en},
                )
                if created:
                    self.stdout.write(f"  Created: {slug}  ({name_bs})")
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped: {slug}  ({name_bs})")
                    skipped_count += 1

        self.stdout.write("")
        summary_msg = (
            f"{'Would create' if dry_run else 'Created'} {created_count}, "
            f"{'would skip' if dry_run else 'skipped'} {skipped_count} "
            f"(total processed: {created_count + skipped_count})."
        )
        self.stdout.write(self.style.SUCCESS(summary_msg))
