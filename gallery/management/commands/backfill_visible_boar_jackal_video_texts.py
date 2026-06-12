from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for confirmed boar and jackal videos."

    VIDEO_TEXTS_BY_CURRENT_TITLE = {
        "Video upload 2026-06-12 13:10": {
            "title_bs": "Divlje svinje u šumi",
            "description_bs": "Krdo divljih svinja se kreće kroz šumski prostor.",
            "title_en": "Wild Boars in Forest",
            "description_en": "A group of wild boars moving through the forest.",
        },
        "Video upload 2026-06-12 12:59": {
            "title_bs": "Prasad divlje svinje",
            "description_bs": "Prasad divlje svinje se hrane uz odrasle jedinke.",
            "title_en": "Wild Boar Piglets",
            "description_en": "Wild boar piglets feeding near adult boars.",
        },
        "Video upload 2026-06-12 12:50": {
            "title_bs": "Divlja svinja s mladima",
            "description_bs": "Divlja svinja se zadržava s mladima u šumskom prostoru.",
            "title_en": "Wild Boar with Young",
            "description_en": "A wild boar staying with young in the forest.",
        },
        "Krmača na planini Plješevici": {
            "title_bs": "Krmača u šumi",
            "description_bs": "Krmača leži i odmara u šumskom prostoru.",
            "title_en": "Sow in Forest",
            "description_en": "A sow lying down and resting in the forest.",
        },
        "Divlja svinja s prasićima": {
            "title_bs": "Divlja svinja s prasićima",
            "description_bs": "Divlja svinja leži s prasićima u šumi.",
            "title_en": "Wild Boar with Piglets",
            "description_en": "A wild boar lying with piglets in the forest.",
        },
        "Video upload 2026-06-12 12:37": {
            "title_bs": "Čagalj kod vode",
            "description_bs": "Čagalj se kreće kod prirodnog blatnjavog pojila tokom noći.",
            "title_en": "Jackal Near Water",
            "description_en": "A jackal moving near a natural muddy waterhole at night.",
        },
        "Video upload 2026-06-12 12:33": {
            "title_bs": "Čagalj noću",
            "description_bs": "Čagalj prolazi kroz šumski prostor tokom noći.",
            "title_en": "Jackal at Night",
            "description_en": "A jackal passing through the forest at night.",
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

        self.stdout.write(
            self.style.WARNING(
                "Matching confirmed boar and jackal videos by current production title..."
            )
        )

        for current_title, text_data in self.VIDEO_TEXTS_BY_CURRENT_TITLE.items():
            matches = VideoClip.objects.filter(title_bs=current_title)

            if not matches.exists():
                self.stdout.write(
                    self.style.ERROR(f'No video found with title_bs="{current_title}".')
                )
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