from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for confirmed lynx videos by production ID."

    VIDEO_TEXTS_BY_ID = {
        66: {
            "title_bs": "Ris noću",
            "description_bs": "Ris se kreće kroz šumski prostor tokom noći.",
            "title_en": "Lynx at Night",
            "description_en": "A lynx moving through the forest at night.",
        },
        64: {
            "title_bs": "Ris u prolazu",
            "description_bs": "Ris prolazi ispred kamere na otvorenom prostoru.",
            "title_en": "Lynx Passing By",
            "description_en": "A lynx passing in front of the camera in an open area.",
        },
        63: {
            "title_bs": "Ris u noćnom snimku",
            "description_bs": "Ris se zadržava u noćnom šumskom snimku.",
            "title_en": "Lynx in Night Footage",
            "description_en": "A lynx recorded in the forest at night.",
        },
        61: {
            "title_bs": "Ris uz šumu",
            "description_bs": "Ris se kreće rubom šumskog prostora.",
            "title_en": "Lynx Near Forest Edge",
            "description_en": "A lynx moving along the forest edge.",
        },
        60: {
            "title_bs": "Ris na putanji",
            "description_bs": "Ris prolazi utabanom šumskom putanjom.",
            "title_en": "Lynx on Trail",
            "description_en": "A lynx walking along a forest trail.",
        },
        59: {
            "title_bs": "Ris u vegetaciji",
            "description_bs": "Ris se kreće kroz nisku šumsku vegetaciju.",
            "title_en": "Lynx in Vegetation",
            "description_en": "A lynx moving through low forest vegetation.",
        },
        58: {
            "title_bs": "Ris uz potok",
            "description_bs": "Ris stoji uz šumski potok i osmatra okolinu.",
            "title_en": "Lynx by Stream",
            "description_en": "A lynx stands near a forest stream and observes the area.",
        },
        57: {
            "title_bs": "Ris u šumi",
            "description_bs": "Ris se kreće kroz šumski teren.",
            "title_en": "Lynx in Forest",
            "description_en": "A lynx moving through forest terrain.",
        },
        56: {
            "title_bs": "Ris na čistini",
            "description_bs": "Ris se zadržava na maloj šumskoj čistini.",
            "title_en": "Lynx in Clearing",
            "description_en": "A lynx staying in a small forest clearing.",
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

        self.stdout.write(self.style.WARNING("Matching confirmed lynx videos by production ID..."))

        for video_id, text_data in self.VIDEO_TEXTS_BY_ID.items():
            video = VideoClip.objects.filter(id=video_id).first()

            if not video:
                self.stdout.write(self.style.ERROR(f"VideoClip ID {video_id} not found. Skipping."))
                skipped_count += 1
                continue

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
                self.style.SUCCESS(f"Done. Updated {updated_count} videos. Skipped {skipped_count}.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. Skipped {skipped_count}. Run with --apply to save changes."
                )
            )