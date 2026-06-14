from django.core.management.base import BaseCommand

from gallery.models import Tag, VideoClip


class Command(BaseCommand):
    help = (
        "Synchronize existing video metadata from album names. "
        "Updates titles when they do not match the album, fills descriptions only when empty, "
        "and adds existing logical tags without removing existing tags. "
        "Does not create tags, upload videos, or touch Cloudflare fields. "
        "Dry-run by default. Use --apply to save changes."
    )

    # Album slug -> logical existing tag slugs.
    # These tags must already exist in admin.
    ALBUM_TAG_SLUGS = {
        "cagalj": ["cagalj", "sisari"],
        "divlje-svinje": ["divlja-svinja", "sisari"],
        "divokoze": ["divokoza", "sisari"],
        "jazavac": ["jazavac", "sisari"],
        "jelen": ["jelen", "sisari"],
        "kuna": ["kuna", "sisari"],
        "lisica": ["lisica", "sisari"],
        "medvjed": ["medvjed", "sisari"],
        "ptice": ["ptice"],
        "ris": ["ris", "sisari"],
        "srna": ["srna", "sisari"],
        "vuk": ["vuk", "sisari"],
        "zec": ["zec", "sisari"],
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
        parser.add_argument(
            "--include-not-ready",
            action="store_true",
            help="Also update uploading/processing/failed videos. Default updates only ready videos.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        include_private = options["include_private"]
        include_not_ready = options["include_not_ready"]

        queryset = VideoClip.objects.select_related("album").prefetch_related("tags").filter(
            album__isnull=False,
        )

        if not include_private:
            queryset = queryset.filter(is_public=True)

        if not include_not_ready:
            queryset = queryset.filter(status=VideoClip.STATUS_READY)

        configured_tag_slugs = set()
        for tag_slugs in self.ALBUM_TAG_SLUGS.values():
            configured_tag_slugs.update(tag_slugs)

        existing_tags_by_slug = {
            tag.slug: tag
            for tag in Tag.objects.filter(slug__in=configured_tag_slugs)
        }

        checked_count = 0
        changed_count = 0
        skipped_count = 0

        self.stdout.write(
            self.style.WARNING(
                "Checking existing video metadata against album names..."
            )
        )

        for video in queryset.order_by("id"):
            checked_count += 1
            album = video.album

            desired_title_bs = album.title_bs or album.title or video.title_bs
            desired_title_en = album.title_en or album.title or video.title_en or desired_title_bs

            desired_description_bs = (
                f"{desired_title_bs}. Snimljeno na području Plješevice kod Bihaća, "
                "Bosna i Hercegovina. Video prikazuje divlje životinje i prirodu Plješevice."
            )

            desired_description_en = (
                f"{desired_title_en}. Recorded in the Plješevica mountain area near Bihać, "
                "Bosnia and Herzegovina. The video shows wildlife and nature of Plješevica."
            )

            desired_tag_slugs = self.ALBUM_TAG_SLUGS.get(album.slug, [])
            existing_video_tag_slugs = set(video.tags.values_list("slug", flat=True))

            available_desired_tag_slugs = [
                slug for slug in desired_tag_slugs if slug in existing_tags_by_slug
            ]

            missing_configured_tag_slugs = [
                slug for slug in desired_tag_slugs if slug not in existing_tags_by_slug
            ]

            missing_video_tag_slugs = [
                slug for slug in available_desired_tag_slugs
                if slug not in existing_video_tag_slugs
            ]

            fields_to_update = []

            if video.title_bs != desired_title_bs:
                fields_to_update.append("title_bs")

            if video.title_en != desired_title_en:
                fields_to_update.append("title_en")

            # Descriptions are filled only when empty.
            # Existing custom descriptions are preserved.
            if not video.description_bs:
                fields_to_update.append("description_bs")

            if not video.description_en:
                fields_to_update.append("description_en")

            has_tag_changes = bool(missing_video_tag_slugs)
            has_changes = bool(fields_to_update or has_tag_changes)

            if not has_changes:
                continue

            self.stdout.write("")
            self.stdout.write(f"Video ID: {video.id}")
            self.stdout.write(f"Album slug: {album.slug}")
            self.stdout.write(f"Album: {album}")

            if "title_bs" in fields_to_update:
                self.stdout.write(f"BS title: {video.title_bs} -> {desired_title_bs}")
            else:
                self.stdout.write(f"BS title: unchanged ({video.title_bs})")

            if "title_en" in fields_to_update:
                self.stdout.write(f"EN title: {video.title_en} -> {desired_title_en}")
            else:
                self.stdout.write(f"EN title: unchanged ({video.title_en})")

            if "description_bs" in fields_to_update:
                self.stdout.write(f"BS description: will fill -> {desired_description_bs}")
            else:
                self.stdout.write("BS description: unchanged")

            if "description_en" in fields_to_update:
                self.stdout.write(f"EN description: will fill -> {desired_description_en}")
            else:
                self.stdout.write("EN description: unchanged")

            if desired_tag_slugs:
                self.stdout.write(f"Configured tags: {', '.join(desired_tag_slugs)}")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "Configured tags: none for this album slug. Title/description can still update."
                    )
                )

            if missing_configured_tag_slugs:
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing existing tag rows, not added: {', '.join(missing_configured_tag_slugs)}"
                    )
                )

            if missing_video_tag_slugs:
                self.stdout.write(f"Tags to add: {', '.join(missing_video_tag_slugs)}")
            else:
                self.stdout.write("Tags to add: none")

            if apply_changes:
                if "title_bs" in fields_to_update:
                    video.title_bs = desired_title_bs

                if "title_en" in fields_to_update:
                    video.title_en = desired_title_en

                if "description_bs" in fields_to_update:
                    video.description_bs = desired_description_bs

                if "description_en" in fields_to_update:
                    video.description_en = desired_description_en

                if fields_to_update:
                    update_fields = fields_to_update + ["updated_at"]
                    video.save(update_fields=update_fields)

                if missing_video_tag_slugs:
                    tag_objects = [
                        existing_tags_by_slug[slug]
                        for slug in missing_video_tag_slugs
                    ]
                    video.tags.add(*tag_objects)

            changed_count += 1

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Checked {checked_count}. Changed {changed_count}. Skipped {skipped_count}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. Checked {checked_count}. Would change {changed_count}. "
                    "Run with --apply to save changes."
                )
            )