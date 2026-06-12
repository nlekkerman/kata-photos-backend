from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for confirmed deer videos by production ID."

    VIDEO_TEXTS_BY_ID = {
        55: {
            "title_bs": "Srne na pojilu",
            "description_bs": "Dvije srne se zadržavaju kod prirodnog pojila.",
            "title_en": "Does at Waterhole",
            "description_en": "Two does staying near a natural waterhole.",
        },
        54: {
            "title_bs": "Srndać na pojilu",
            "description_bs": "Srndać pije vodu iz prirodnog blatnjavog pojila.",
            "title_en": "Roe Buck at Waterhole",
            "description_en": "A roe buck drinking from a natural muddy waterhole.",
        },
        53: {
            "title_bs": "Srndać u šumi",
            "description_bs": "Srndać se hrani u šumskom prostoru.",
            "title_en": "Roe Buck in Forest",
            "description_en": "A roe buck feeding in the forest.",
        },
        52: {
            "title_bs": "Oprezna srna",
            "description_bs": "Srna oprezno stoji i osluškuje okolinu.",
            "title_en": "Cautious Doe",
            "description_en": "A doe stands alert and listens to the surroundings.",
        },
        51: {
            "title_bs": "Dvije srne u šumi",
            "description_bs": "Dvije srne se kreću kroz šumski prostor.",
            "title_en": "Two Does in Forest",
            "description_en": "Two does moving through the forest.",
        },
        50: {
            "title_bs": "Srndać na pojilu",
            "description_bs": "Srndać pije vodu iz prirodnog blatnjavog pojila.",
            "title_en": "Roe Buck at Waterhole",
            "description_en": "A roe buck drinking from a natural muddy waterhole.",
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

        self.stdout.write(self.style.WARNING("Matching confirmed videos by production ID..."))

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