from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for confirmed fox videos by current production title."

    VIDEO_TEXTS_BY_CURRENT_TITLE = {
        "Video upload 2026-06-12 13:18": {
            "title_bs": "Lisica kod pojila",
            "description_bs": "Lisica se kreće uz prirodno blatnjavo pojilo.",
            "title_en": "Fox at Waterhole",
            "description_en": "A fox moving near a natural muddy waterhole.",
        },
        "Video upload 2026-06-12 13:15": {
            "title_bs": "Lisica uz blatnjavo pojilo",
            "description_bs": "Lisica prolazi pored prirodnog blatnjavog pojila u šumi.",
            "title_en": "Fox by Muddy Waterhole",
            "description_en": "A fox passing by a natural muddy waterhole in the forest.",
        },
        "Video upload 2026-06-12 13:13": {
            "title_bs": "Lisica odmara u šumi",
            "description_bs": "Lisica leži i odmara u šumskom prostoru.",
            "title_en": "Fox Resting in Forest",
            "description_en": "A fox lying down and resting in the forest.",
        },
        "Video upload 2026-06-12 13:12": {
            "title_bs": "Lisica kod vode",
            "description_bs": "Lisica se zadržava kod male blatnjave vode u šumi.",
            "title_en": "Fox Near Water",
            "description_en": "A fox staying near a small muddy waterhole in the forest.",
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually update the videos. Without this flag, command only previews changes.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        updated_count = 0
        skipped_count = 0

        self.stdout.write(self.style.WARNING("Matching confirmed fox videos by current production title..."))

        for current_title, text_data in self.VIDEO_TEXTS_BY_CURRENT_TITLE.items():
            matches = VideoClip.objects.filter(title_bs=current_title)

            if not matches.exists():
                self.stdout.write(self.style.ERROR(f'No video found with title_bs="{current_title}".'))
                skipped_count += 1
                continue

            if matches.count() > 1:
                self.stdout.write(
                    self.style.ERROR(
                        f'Multiple videos found with title_bs="{current_title}". Skipping.'
                    )
                )
                skipped_count += 1
                continue

            video = matches.first()

            self.stdout.write("")
            self.stdout.write(f"Matched video ID: {video.id}")
            self.stdout.write(f"Current title_bs: {video.title_bs}")
            self.stdout.write(f"Current title_en: {video.title_en}")
            self.stdout.write(f"New title_bs: {text_data['title_bs']}")
            self.stdout.write(f"New title_en: {text_data['title_en']}")

            if apply_changes:
                video.title_bs = text_data["title_bs"]
                video.description_bs = text_data["description_bs"]
                video.title_en = text_data["title_en"]
                video.description_en = text_data["description_en"]

                video.save(
                    update_fields=[
                        "title_bs",
                        "description_bs",
                        "title_en",
                        "description_en",
                        "updated_at",
                    ]
                )
                updated_count += 1

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated_count} videos. Skipped {skipped_count}."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. Skipped {skipped_count}. Run with --apply to save changes."
                )
            )