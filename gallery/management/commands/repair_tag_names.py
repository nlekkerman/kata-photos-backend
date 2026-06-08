"""
Management command: repair_tag_names

Fixes mojibake-encoded Bosnian tag name_bs values that were stored with broken
Windows-1252 → UTF-8 double-encoding artefacts, e.g. "─îaplja" instead of "Čaplja".

Strategy: look up each tag by its slug (slugs are already correct) and overwrite
name_bs with the correct UTF-8 value when it does not already match.

Safe to run multiple times — tags that already have the correct name are skipped.
No tags are ever deleted; no IDs or relations change.

Usage:
    python manage.py repair_tag_names
    python manage.py repair_tag_names --dry-run
"""

from django.core.management.base import BaseCommand

from gallery.models import Tag

# ---------------------------------------------------------------------------
# Mapping: slug → correct Bosnian name_bs
# Slugs are stable (already correct in DB); only name_bs needs repair.
# ---------------------------------------------------------------------------

REPAIRS = {
    "bjelouska":         "Bjelouška",
    "caplja":            "Čaplja",
    "crni-dazdevnjak":   "Crni daždevnjak",
    "crvendac":          "Crvendać",
    "cuk":               "Ćuk",
    "dazdevnjak":        "Daždevnjak",
    "divlja-macka":      "Divlja mačka",
    "djetlic":           "Djetlić",
    "gusteri":           "Gušteri",
    "jez":               "Jež",
    "krastace":          "Krastače",
    "misar":             "Mišar",
    "mladuncad":         "Mladunčad",
    "nocne-zivotinje":   "Noćne životinje",
    "nocni-snimci":      "Noćni snimci",
    "pcele":             "Pčele",
    "pecina":            "Pećina",
    "puzevi":            "Puževi",
    "rijecne-zivotinje": "Riječne životinje",
    "sismisi":           "Šišmiši",
    "smedi-medvjed":     "Smeđi medvjed",
    "suma":              "Šuma",
    "sumske-zivotinje":  "Šumske životinje",
    "tragovi-zivotinja": "Tragovi životinja",
    "zabe":              "Žabe",
    "zelembac":          "Zelembać",
}


class Command(BaseCommand):
    help = (
        "Repair mojibake-encoded Bosnian tag name_bs values. "
        "Tags are looked up by slug; only name_bs is updated. "
        "Safe to run multiple times."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes will be written.\n"))

        repaired = 0
        already_correct = 0
        missing = 0

        for slug, correct_name_bs in sorted(REPAIRS.items()):
            try:
                tag = Tag.objects.get(slug=slug)
            except Tag.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"  [missing]  slug={slug!r}  — tag not found, skipping")
                )
                missing += 1
                continue

            if tag.name_bs == correct_name_bs:
                self.stdout.write(f"  [ok]       slug={slug!r}  name_bs already correct")
                already_correct += 1
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [would fix] slug={slug!r}\n"
                        f"              was:  {tag.name_bs!r}\n"
                        f"              will: {correct_name_bs!r}"
                    )
                )
                repaired += 1
            else:
                old = tag.name_bs
                tag.name_bs = correct_name_bs
                tag.save(update_fields=["name_bs", "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [fixed]    slug={slug!r}\n"
                        f"             was:  {old!r}\n"
                        f"             now:  {correct_name_bs!r}"
                    )
                )
                repaired += 1

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete: {repaired} would be repaired, "
                    f"{already_correct} already correct, {missing} missing."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done: {repaired} repaired, {already_correct} already correct, {missing} missing."
                )
            )
