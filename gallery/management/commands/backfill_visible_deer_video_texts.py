from django.core.management.base import BaseCommand

from gallery.models import VideoClip


class Command(BaseCommand):
    help = "Backfill BS/EN titles and descriptions for selected deer videos by current title/name."

    VIDEO_TEXTS_BY_CURRENT_TITLE = {
        # Match these to the CURRENT title visible in admin/site.
        # Keep them exactly as they appear before update.

        "Video upload 2026-06-11 10:37": {
            "title_bs": "Srne na pojilu",
            "description_bs": "Dvije srne se zadržavaju kod prirodnog pojila.",
            "title_en": "Does at Waterhole",
            "description_en": "Two does staying near a natural waterhole.",
        },
        "Video upload 2026-06-11 11:03": {
            "title_bs": "Srndać na pojilu",
            "description_bs": "Srndać pije vodu iz prirodnog blatnjavog pojila.",
            "title_en": "Roe Buck at Waterhole",
            "description_en": "A roe buck drinking from a natural muddy waterhole.",
        },
        "Video upload 2026-06-11 10:49": {
            "title_bs": "Srndać u šumi",
            "description_bs": "Srndać se hrani u šumskom prostoru.",
            "title_en": "Roe Buck in Forest",
            "description_en": "A roe buck feeding in the forest.",
        },
        "Video upload 2026-06-11 16:46": {
            "title_bs": "Oprezna srna",
            "description_bs": "Srna oprezno stoji i osluškuje okolinu.",
            "title_en": "Cautious Doe",
            "description_en": "A doe stands alert and listens to the surroundings.",
        },
        "Video upload 2026-06-11 16:42": {
            "title_bs": "Dvije srne u šumi",
            "description_bs": "Dvije srne se kreću kroz šumski prostor.",
            "title_en": "Two Does in Forest",
            "description_en": "Two does moving through the forest.",
        },
        # This one is already titled, but this fills EN + descriptions too.
        "Srndać na pojilu": {
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

        self.stdout.write(self.style.WARNING("Matching selected videos by current title_bs..."))

        for current_title, text_data in self.VIDEO_TEXTS_BY_CURRENT_TITLE.items():
            matches = VideoClip.objects.filter(title_bs=current_title)

            if not matches.exists():
                self.stdout.write(self.style.ERROR(f'No video found with title_bs="{current_title}".'))
                skipped_count += 1
                continue

            if matches.count() > 1:
                self.stdout.write(
                    self.style.ERROR(
                        f'Multiple videos found with title_bs="{current_title}". '
                        "Skipping to avoid updating the wrong video."
                    )
                )
                skipped_count += 1
                continue

            video = matches.first()

            self.stdout.write("")
            self.stdout.write(f"Matched video ID: {video.id}")
            self.stdout.write(f"Current title_bs: {video.title_bs}")
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