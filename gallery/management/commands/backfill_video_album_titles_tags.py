from django.core.management.base import BaseCommand

from gallery.models import Tag, VideoClip


class Command(BaseCommand):
    help = (
        "Backfill existing video titles/descriptions from album names and attach existing logical tags. "
        "Does not create tags and does not upload videos. "
        "Dry-run by default. Use --apply to save changes."
    )

    # No broad SEO/location base tags here.
    # Location/SEO words are handled in the description, not repeated as tags.
    BASE_TAG_SLUGS = []

    # Match album names/titles/slugs to existing tag slugs.
    # These slugs must already exist in admin.
    ALBUM_TAG_RULES = {
        "lisica": ["lisica", "sisari"],
        "red fox": ["lisica", "sisari"],
        "fox": ["lisica", "sisari"],

        "vuk": ["vuk", "sisari"],
        "wolf": ["vuk", "sisari"],

        "zec": ["zec", "sisari"],
        "hare": ["zec", "sisari"],

        "kuna": ["kuna", "sisari"],
        "marten": ["kuna", "sisari"],

        "srna": ["srna", "sisari"],
        "roe deer": ["srna", "sisari"],

        "jelen": ["jelen", "sisari"],
        "red deer": ["jelen", "sisari"],

        "divlja svinja": ["divlja-svinja", "sisari"],
        "divlje svinje": ["divlja-svinja", "sisari"],
        "wild boar": ["divlja-svinja", "sisari"],
        "wild boars": ["divlja-svinja", "sisari"],

        "medvjed": ["medvjed", "sisari"],
        "smeđi medvjed": ["medvjed", "sisari"],
        "brown bear": ["medvjed", "sisari"],

        "čagalj": ["cagalj", "sisari"],
        "cagalj": ["cagalj", "sisari"],
        "jackal": ["cagalj", "sisari"],

        "ris": ["ris", "sisari"],
        "lynx": ["ris", "sisari"],

        "ptice": ["ptice"],
        "birds": ["ptice"],

        "sova": ["sova", "sove", "ptice"],
        "owl": ["sova", "sove", "ptice"],

        "čaplja": ["caplja", "ptice", "vodene-ptice"],
        "caplja": ["caplja", "ptice", "vodene-ptice"],
        "heron": ["caplja", "ptice", "vodene-ptice"],

        "zmije": ["zmije", "gmizavci"],
        "snake": ["zmije", "gmizavci"],

        "gušteri": ["gusteri", "gmizavci"],
        "gusteri": ["gusteri", "gmizavci"],
        "lizard": ["gusteri", "gmizavci"],

        "žabe": ["zabe", "vodozemci"],
        "zabe": ["zabe", "vodozemci"],
        "frog": ["zabe", "vodozemci"],

        "insekti": ["insekti"],
        "insects": ["insekti"],
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually update videos. Without this flag, command only previews changes.",
        )
        parser.add_argument(
            "--include-private",
            action="store_true",
            help="Also update videos that are not public.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        include_private = options["include_private"]

        queryset = VideoClip.objects.select_related("album").prefetch_related("tags").filter(
            status=VideoClip.STATUS_READY,
            album__isnull=False,
        )

        if not include_private:
            queryset = queryset.filter(is_public=True)

        all_required_slugs = set(self.BASE_TAG_SLUGS)
        for slugs in self.ALBUM_TAG_RULES.values():
            all_required_slugs.update(slugs)

        existing_tags = {
            tag.slug: tag
            for tag in Tag.objects.filter(slug__in=all_required_slugs)
        }

        updated_count = 0
        skipped_count = 0

        self.stdout.write(
            self.style.WARNING(
                "Backfilling existing video titles/descriptions/tags from albums..."
            )
        )

        for video in queryset.order_by("id"):
            album = video.album

            title_bs = album.title_bs or album.title or video.title_bs
            title_en = album.title_en or album.title or video.title_en or title_bs

            album_key_parts = [
                album.slug or "",
                album.title_bs or "",
                album.title_en or "",
                album.title or "",
            ]
            album_key = " ".join(album_key_parts).lower()

            tag_slugs = list(self.BASE_TAG_SLUGS)

            for keyword, slugs in self.ALBUM_TAG_RULES.items():
                if keyword in album_key:
                    tag_slugs.extend(slugs)

            tag_slugs = list(dict.fromkeys(tag_slugs))

            if not tag_slugs:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        f"Video ID {video.id}: no matching tag rule for album '{album}'. Skipping."
                    )
                )
                skipped_count += 1
                continue

            missing_video_slugs = [
                slug for slug in tag_slugs if slug not in existing_tags
            ]

            if missing_video_slugs:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        f"Video ID {video.id}: missing existing tags {missing_video_slugs}. Skipping."
                    )
                )
                skipped_count += 1
                continue

            description_bs = (
                f"{title_bs}. Snimljeno na području Plješevice kod Bihaća, "
                "Bosna i Hercegovina. Video prikazuje divlje životinje i prirodu Plješevice."
            )

            description_en = (
                f"{title_en}. Recorded in the Plješevica mountain area near Bihać, "
                "Bosnia and Herzegovina. The video shows wildlife and nature of Plješevica."
            )

            self.stdout.write("")
            self.stdout.write(f"Video ID: {video.id}")
            self.stdout.write(f"Album: {album}")
            self.stdout.write(f"Old BS title: {video.title_bs}")
            self.stdout.write(f"New BS title: {title_bs}")
            self.stdout.write(f"Old EN title: {video.title_en}")
            self.stdout.write(f"New EN title: {title_en}")
            self.stdout.write(f"New BS description: {description_bs}")
            self.stdout.write(f"New EN description: {description_en}")
            self.stdout.write(f"Tags: {', '.join(tag_slugs)}")

            if apply_changes:
                video.title_bs = title_bs
                video.title_en = title_en
                video.description_bs = description_bs
                video.description_en = description_en

                video.save(
                    update_fields=[
                        "title_bs",
                        "title_en",
                        "description_bs",
                        "description_en",
                        "updated_at",
                    ]
                )

                tag_objects = [existing_tags[slug] for slug in tag_slugs]
                video.tags.set(tag_objects)

                updated_count += 1

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Updated {updated_count}. Skipped {skipped_count}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. Would update {queryset.count() - skipped_count}. "
                    f"Skipped {skipped_count}. Run with --apply to save changes. "
                    "Use --include-private if you want private/non-public ready videos too."
                )
            )