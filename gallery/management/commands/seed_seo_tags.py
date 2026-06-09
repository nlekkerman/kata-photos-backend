"""
Management command: seed_seo_tags

Seeds a curated set of bilingual SEO tags for Plješevica / Una region
wildlife content.

Behaviour:
  - Uses update_or_create by slug — never duplicates tags.
  - Runs that slug already exists: updates name_bs, name_en,
    description_bs, description_en, and category.
  - Safe to run multiple times.
  - Prints a summary: created / updated / unchanged.

Usage:
    python manage.py seed_seo_tags
    python manage.py seed_seo_tags --dry-run
"""

from django.core.management.base import BaseCommand

from gallery.models import Tag

# ---------------------------------------------------------------------------
# Seed data
# Each entry: (slug, name_bs, name_en, description_bs, description_en, category)
# ---------------------------------------------------------------------------
SEED_TAGS = [
    # ---- Locations ----------------------------------------------------------
    (
        'bosna-i-hercegovina',
        'Bosna i Hercegovina',
        'Bosnia and Herzegovina',
        'Bosna i Hercegovina — zemlja nevjerovatne prirodne raznovrsnosti.',
        'Bosnia and Herzegovina — a land of extraordinary natural diversity.',
        Tag.CATEGORY_LOCATION,
    ),
    (
        'bihac',
        'Bihać',
        'Bihać',
        'Bihać — grad na rijeci Uni, kapija Une i Plješevice.',
        'Bihać — city on the Una River, gateway to Una and Plješevica.',
        Tag.CATEGORY_LOCATION,
    ),
    (
        'pljesevica',
        'Plješevica',
        'Plješevica Mountain',
        'Planina Plješevica — staništu medvjeda, vukova i divljih svinja na granici BiH i Hrvatske.',
        'Plješevica Mountain — habitat of bears, wolves and wild boar on the BiH–Croatia border.',
        Tag.CATEGORY_LOCATION,
    ),
    (
        'una-national-park',
        'Nacionalni park Una',
        'Una National Park',
        'Nacionalni park Una — zaštićeno područje kristalno čiste rijeke Une u sjeverozapadnoj Bosni.',
        'Una National Park — protected area of the crystal-clear Una River in north-west Bosnia.',
        Tag.CATEGORY_LOCATION,
    ),
    (
        'rijeka-una',
        'Rijeka Una',
        'Una River',
        'Rijeka Una — jedna od najčišćih rijeka u Bosni i Hercegovini.',
        'Una River — one of the cleanest rivers in Bosnia and Herzegovina.',
        Tag.CATEGORY_LOCATION,
    ),
    # ---- Species ------------------------------------------------------------
    (
        'medvjed',
        'Smeđi medvjed',
        'Brown Bear',
        'Smeđi medvjed (Ursus arctos) — jedan od najvećih predatora Balkana.',
        'Brown bear (Ursus arctos) — one of the largest predators of the Balkans.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'divlja-svinja',
        'Divlja svinja',
        'Wild Boar',
        'Divlja svinja (Sus scrofa) — čest stanovnik šuma Plješevice i Une.',
        'Wild boar (Sus scrofa) — a common inhabitant of Plješevica and Una forests.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'lisica',
        'Lisica',
        'Red Fox',
        'Lisica (Vulpes vulpes) — lukavi i prilagodljivi predator.',
        'Red fox (Vulpes vulpes) — cunning and adaptable predator.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'srna',
        'Srna',
        'Roe Deer',
        'Srna (Capreolus capreolus) — najmanji europski jelen, česta u šumskim rubovima.',
        'Roe deer (Capreolus capreolus) — smallest European deer, common at forest edges.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'ptice',
        'Ptice',
        'Birds',
        'Divlje ptice — raznovrsni ptičji svijet Plješevice i Une.',
        'Wild birds — the diverse avian world of Plješevica and Una.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'sisari',
        'Sisari',
        'Mammals',
        'Sisari — divlji sisavci Dinarskog gorja i rijeke Une.',
        'Mammals — wild mammals of the Dinaric mountains and Una River.',
        Tag.CATEGORY_SPECIES,
    ),
    # ---- Habitats -----------------------------------------------------------
    (
        'suma',
        'Šuma',
        'Forest',
        'Šuma — gusti šumski pokrivač Plješevice i okolnih planina.',
        'Forest — the dense woodland cover of Plješevica and surrounding mountains.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'planina',
        'Planina',
        'Mountain',
        'Planinski ekosistem — staništa na većim nadmorskim visinama Plješevice.',
        'Mountain ecosystem — high-altitude habitats on Plješevica.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'greben',
        'Greben',
        'Ridge',
        'Planinski grebeni — izložene kamene formacije i otvoreni predjeli.',
        'Mountain ridges — exposed rock formations and open terrain.',
        Tag.CATEGORY_HABITAT,
    ),
    # ---- Behaviour ----------------------------------------------------------
    (
        'hranjenje',
        'Hranjenje',
        'Feeding',
        'Snimci hranjenja divljih životinja — rijetki i dragocjeni trenuci.',
        'Footage of wild animals feeding — rare and precious moments.',
        Tag.CATEGORY_BEHAVIOR,
    ),
    (
        'mladuncad',
        'Mladunčad',
        'Young Animals',
        'Mladunčad divljih životinja — najmlađa generacija šumskih stanovnika.',
        'Young wild animals — the newest generation of forest inhabitants.',
        Tag.CATEGORY_BEHAVIOR,
    ),
    (
        'tragovi-zivotinja',
        'Tragovi životinja',
        'Animal Tracks',
        'Otisci i tragovi divljih životinja — dokazi prisutnosti u prirodi.',
        'Prints and tracks of wild animals — evidence of presence in nature.',
        Tag.CATEGORY_BEHAVIOR,
    ),
]


class Command(BaseCommand):
    help = (
        "Seed bilingual SEO tags for Plješevica / Una wildlife content. "
        "Safe to run multiple times — uses update_or_create by slug."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            default=False,
            help="Print what would happen without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes will be written.\n"))

        created_count = 0
        updated_count = 0
        unchanged_count = 0

        for slug, name_bs, name_en, description_bs, description_en, category in SEED_TAGS:
            defaults = {
                "name_bs": name_bs,
                "name_en": name_en,
                "description_bs": description_bs,
                "description_en": description_en,
                "category": category,
            }

            if dry_run:
                try:
                    existing = Tag.objects.get(slug=slug)
                    changed = any(
                        getattr(existing, field) != value
                        for field, value in defaults.items()
                    )
                    if changed:
                        self.stdout.write(f"  [update]   {slug}")
                        updated_count += 1
                    else:
                        self.stdout.write(f"  [unchanged] {slug}")
                        unchanged_count += 1
                except Tag.DoesNotExist:
                    self.stdout.write(f"  [create]   {slug}")
                    created_count += 1
            else:
                tag, created = Tag.objects.get_or_create(slug=slug, defaults=defaults)
                if created:
                    self.stdout.write(f"  Created:   {slug}  ({name_bs})")
                    created_count += 1
                else:
                    # Check if any field differs and update if so.
                    changed_fields = []
                    for field, value in defaults.items():
                        if getattr(tag, field) != value:
                            setattr(tag, field, value)
                            changed_fields.append(field)
                    if changed_fields:
                        tag.save(update_fields=changed_fields)
                        self.stdout.write(f"  Updated:   {slug}  (fields: {', '.join(changed_fields)})")
                        updated_count += 1
                    else:
                        self.stdout.write(f"  Unchanged: {slug}")
                        unchanged_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — created: {created_count}, updated: {updated_count}, "
                f"unchanged: {unchanged_count}."
            )
        )
