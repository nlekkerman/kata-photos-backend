from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for confirmed wolf videos by current production title."

    VIDEO_TEXTS_BY_CURRENT_TITLE = {
        "Video upload 2026-06-12 11:35": {
            "title_bs": "Vukovi na pojilu",
            "description_bs": "Dva vuka se zadržavaju kod prirodnog blatnjavog pojila.",
            "title_en": "Wolves at Waterhole",
            "description_en": "Two wolves staying near a natural muddy waterhole.",
        },
        "Video upload 2026-06-12 11:20": {
            "title_bs": "Vuk kod pojila",
            "description_bs": "Vuk stoji uz prirodno blatnjavo pojilo u šumi.",
            "title_en": "Wolf at Waterhole",
            "description_en": "A wolf standing near a natural muddy waterhole in the forest.",
        },
        "Vukovi": {
            "title_bs": "Vukovi u šumi",
            "description_bs": "Vukovi se kreću kroz šumski prostor kod blatnjavog pojila.",
            "title_en": "Wolves in Forest",
            "description_en": "Wolves moving through the forest near a muddy waterhole.",
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

        self.stdout.write(self.style.WARNING("Matching confirmed wolf videos by current production title..."))

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
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Updated {updated_count} videos. Skipped {skipped_count}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. Skipped {skipped_count}. Run with --apply to save changes."
                )
            )