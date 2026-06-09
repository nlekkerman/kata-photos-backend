"""
Management command: seed_seo_tags

Canonical idempotent normalizer for SEO/category tags for the
Plješevica / Una region wildlife content.

Behaviour:
  - Updates existing tags by slug (name, descriptions, category).
  - Creates missing tags.
  - Never duplicates tags.
  - Merges known duplicate slugs into their canonical equivalent and
    moves all M2M relationships before deleting the old tag.
  - Safe to run multiple times.
  - Prints a summary: created / updated / unchanged / merged / manual_review.

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
        'Planina Plješevica — stanište medvjeda, vukova i divljih svinja na granici BiH i Hrvatske.',
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
        'vuk',
        'Vuk',
        'Wolf',
        'Vuk (Canis lupus) — vrhovni predator dinarskih šuma.',
        'Wolf (Canis lupus) — apex predator of the Dinaric forests.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'ris',
        'Ris',
        'Eurasian Lynx',
        'Euroazijski ris (Lynx lynx) — najugroženija velika mačka Balkana.',
        'Eurasian lynx (Lynx lynx) — the most endangered large cat of the Balkans.',
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
        'jelen',
        'Jelen',
        'Red Deer',
        'Jelen (Cervus elaphus) — najveći jelen Balkana, čest na Plješevici.',
        'Red deer (Cervus elaphus) — the largest deer of the Balkans, common on Plješevica.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'divokoza',
        'Divokoza',
        'Chamois',
        'Divokoza (Rupicapra rupicapra) — brza planinska antilopa dinarskih grebena.',
        'Chamois (Rupicapra rupicapra) — agile mountain antelope of the Dinaric ridges.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'jazavac',
        'Jazavac',
        'Badger',
        'Jazavac (Meles meles) — noćni stanovnik šuma i livada.',
        'Badger (Meles meles) — nocturnal inhabitant of forests and meadows.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'kuna',
        'Kuna',
        'Marten',
        'Kuna (Martes sp.) — spretni lovac šumskih krošnji.',
        'Marten (Martes sp.) — agile predator of forest canopies.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'vidra',
        'Vidra',
        'Otter',
        'Vidra (Lutra lutra) — rijetki stanovnik čistih rijeka Une i njezinih pritoka.',
        'Otter (Lutra lutra) — rare inhabitant of the clean Una River and its tributaries.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'divlja-macka',
        'Divlja mačka',
        'Wildcat',
        'Divlja mačka (Felis silvestris) — rijetki tajnoviti predator dinarskih šuma.',
        'Wildcat (Felis silvestris) — rare and secretive predator of Dinaric forests.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'zec',
        'Zec',
        'Hare',
        'Zec (Lepus europaeus) — brzi stanovnik šumskih rubova i livada.',
        'Hare (Lepus europaeus) — fast-moving inhabitant of forest edges and meadows.',
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
        'vodene-ptice',
        'Vodene ptice',
        'Water Birds',
        'Vodene ptice — vrste vezane uz rijeke, potoke i bare.',
        'Water birds — species associated with rivers, streams and wetlands.',
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
    (
        'gmizavci',
        'Gmizavci',
        'Reptiles',
        'Gmizavci — zmije, gušteri i kornjače dinarskog područja.',
        'Reptiles — snakes, lizards and tortoises of the Dinaric region.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'vodozemci',
        'Vodozemci',
        'Amphibians',
        'Vodozemci — žabe, daždevnjaci i vodenjaci rijeke Une i okolnih područja.',
        'Amphibians — frogs, salamanders and newts of the Una River and surrounding areas.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'ribe',
        'Ribe',
        'Fish',
        'Ribe — pastrmka, lipljen i druge vrste čistih rijeka.',
        'Fish — trout, grayling and other species of clean rivers.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'insekti',
        'Insekti',
        'Insects',
        'Insekti — bogat insektni svijet planinskih livada i šuma.',
        'Insects — the rich insect life of mountain meadows and forests.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'sumske-zivotinje',
        'Šumske životinje',
        'Forest Animals',
        'Šumske životinje — sve vrste koje žive u gustim šumama Plješevice.',
        'Forest animals — all species that inhabit the dense forests of Plješevica.',
        Tag.CATEGORY_SPECIES,
    ),
    (
        'rijecne-zivotinje',
        'Riječne životinje',
        'River Animals',
        'Riječne životinje — vrste vezane uz rijeku Unu i njezine pritoke.',
        'River animals — species associated with the Una River and its tributaries.',
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
    (
        'rijeka',
        'Rijeka',
        'River',
        'Riječni ekosistem — staništa uz tekuće vode.',
        'River ecosystem — habitats along running water.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'potok',
        'Potok',
        'Stream',
        'Planinski potoci — hladne, brze i čiste vode dinarskog gorja.',
        'Mountain streams — cold, fast and clean waters of the Dinaric mountains.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'kanjon',
        'Kanjon',
        'Canyon',
        'Kanjon — duboko usječene doline rijeke Une i njezinih pritoka.',
        'Canyon — deeply incised valleys of the Una River and its tributaries.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'pecina',
        'Pećina',
        'Cave',
        'Pećine i špiljski sustavi — stanište šišmiša i drugih podzemnih vrsta.',
        'Caves and cave systems — habitat of bats and other subterranean species.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'livada',
        'Livada',
        'Meadow',
        'Planinske livade — bogata staništa cvijeća, insekata i malih sisavaca.',
        'Mountain meadows — rich habitats of wildflowers, insects and small mammals.',
        Tag.CATEGORY_HABITAT,
    ),
    (
        'snijeg',
        'Snijeg',
        'Snow',
        'Snijegom pokriveni predjeli — zimska staništa i tragovi u snijegu.',
        'Snow-covered terrain — winter habitats and tracks in the snow.',
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
    (
        'nocne-zivotinje',
        'Noćne životinje',
        'Nocturnal Animals',
        'Noćne životinje — vrste aktivne noću, snimljene fotokamerama.',
        'Nocturnal animals — species active at night, captured by camera traps.',
        Tag.CATEGORY_BEHAVIOR,
    ),
    (
        'migracija',
        'Migracija',
        'Migration',
        'Migracija — sezonska kretanja divljih životinja.',
        'Migration — seasonal movements of wild animals.',
        Tag.CATEGORY_BEHAVIOR,
    ),
    # ---- Content type -------------------------------------------------------
    (
        'nocni-snimci',
        'Noćni snimci',
        'Night Footage',
        'Noćni snimci — materijal snimljen noću ili infracrvenim kamerama.',
        'Night footage — material captured at night or with infrared cameras.',
        Tag.CATEGORY_CONTENT_TYPE,
    ),
    (
        'jutarnji-snimci',
        'Jutarnji snimci',
        'Morning Footage',
        'Jutarnji snimci — materijal snimljen u ranu zoru.',
        'Morning footage — material captured at early dawn.',
        Tag.CATEGORY_CONTENT_TYPE,
    ),
]

# ---------------------------------------------------------------------------
# Known duplicate slugs that should be merged into a canonical slug.
# Format: {old_slug: canonical_slug}
# The canonical slug must appear in SEED_TAGS above.
# ---------------------------------------------------------------------------
MERGES = {
    'smedi-medvjed': 'medvjed',
    'divlje-svinje': 'divlja-svinja',
}


class Command(BaseCommand):
    help = (
        "Canonical idempotent normalizer for SEO/category tags. "
        "Safe to run multiple times — updates by slug, merges duplicates."
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

        # Merge duplicates.
        self.stdout.write("")
        merged_count, manual_review_count = self._handle_merges(dry_run)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — created: {created_count}, updated: {updated_count}, "
                f"unchanged: {unchanged_count}, merged: {merged_count}, "
                f"manual_review: {manual_review_count}."
            )
        )

    def _handle_merges(self, dry_run):
        """Merge old duplicate slugs into their canonical equivalents."""
        merged_count = 0
        manual_review_count = 0

        for old_slug, canonical_slug in MERGES.items():
            try:
                old_tag = Tag.objects.get(slug=old_slug)
            except Tag.DoesNotExist:
                self.stdout.write(f"  [merge-skip]  {old_slug} — not found, nothing to merge.")
                continue

            try:
                canonical_tag = Tag.objects.get(slug=canonical_slug)
            except Tag.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [merge-error] {old_slug} → {canonical_slug}: "
                        f"canonical tag not found. Skipping."
                    )
                )
                manual_review_count += 1
                continue

            album_qs = old_tag.albums.all()
            video_qs = old_tag.video_clips.all()
            media_qs = old_tag.media_items.all()
            total_relations = album_qs.count() + video_qs.count() + media_qs.count()

            if dry_run:
                action = "merge+delete" if total_relations == 0 else f"move {total_relations} relation(s) then delete"
                self.stdout.write(
                    f"  [merge-dry]   {old_slug} → {canonical_slug}  ({action})"
                )
                merged_count += 1
                continue

            # Move M2M relationships to canonical tag.
            for album in album_qs:
                album.tags.add(canonical_tag)
                album.tags.remove(old_tag)
            for video in video_qs:
                video.tags.add(canonical_tag)
                video.tags.remove(old_tag)
            for media in media_qs:
                media.tags.add(canonical_tag)
                media.tags.remove(old_tag)

            old_tag.delete()
            self.stdout.write(
                f"  Merged:    {old_slug} → {canonical_slug}  "
                f"(moved {total_relations} relation(s), deleted old tag)"
            )
            merged_count += 1

        return merged_count, manual_review_count
