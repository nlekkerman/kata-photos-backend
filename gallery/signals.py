"""
Post-save signals that trigger Bosnian → English auto-translation.

Translation fires when:
  - A full model save occurs (update_fields is None)
  - At least one Bosnian field has content
  - The matching English field is blank

Translation is intentionally skipped when:
  - update_fields is not None  (partial saves, status updates, our own follow-up saves)
  - English field already has content
  - OPENAI_API_KEY is not configured
  - Any OpenAI error occurs (content saves normally; English stays blank)

Models covered:
  - VideoClip    : title, description
  - Album        : title, description, seo_title, seo_description
  - MediaItem    : title, description, alt_text, caption
  - FieldNote    : excerpt only (title_en and body_en are required non-blank fields
                   that must be filled manually; a schema migration would be needed
                   before those can be auto-translated)
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _needs_translation(bs_value: str, en_value: str) -> bool:
    """Return True if Bosnian has content but English is blank."""
    return bool(bs_value and bs_value.strip()) and not bool(en_value and en_value.strip())


def _apply_translation(instance, field_pairs: list) -> None:
    """
    Collect fields that need translation, call the service, and save results.

    field_pairs: list of (bs_field_name, en_field_name) tuples.
    Uses save(update_fields=...) to avoid triggering translation again.
    """
    from .services.translation import translate_bs_to_en_fields

    to_translate = {
        bs_field: getattr(instance, bs_field)
        for bs_field, en_field in field_pairs
        if _needs_translation(
            getattr(instance, bs_field, ""),
            getattr(instance, en_field, ""),
        )
    }

    if not to_translate:
        return

    bs_to_en = {bs: en for bs, en in field_pairs}
    translated = translate_bs_to_en_fields(to_translate)

    if not translated:
        return

    updated_fields = []
    for bs_field, en_text in translated.items():
        en_field = bs_to_en.get(bs_field)
        if en_field:
            setattr(instance, en_field, en_text)
            updated_fields.append(en_field)

    if updated_fields:
        # update_fields prevents this save from re-triggering translation signals.
        instance.save(update_fields=updated_fields)
        logger.info(
            "%s pk=%s — auto-translated: %s",
            instance.__class__.__name__,
            instance.pk,
            updated_fields,
        )


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender='gallery.VideoClip')
def translate_video_clip(sender, instance, update_fields, **kwargs):
    # Skip partial saves (including our own follow-up update_fields save).
    if update_fields is not None:
        return
    _apply_translation(instance, [
        ('title_bs', 'title_en'),
        ('description_bs', 'description_en'),
    ])


@receiver(post_save, sender='gallery.Album')
def translate_album(sender, instance, update_fields, **kwargs):
    if update_fields is not None:
        return
    _apply_translation(instance, [
        ('title_bs', 'title_en'),
        ('description_bs', 'description_en'),
        ('seo_title_bs', 'seo_title_en'),
        ('seo_description_bs', 'seo_description_en'),
    ])


@receiver(post_save, sender='gallery.MediaItem')
def translate_media_item(sender, instance, update_fields, **kwargs):
    if update_fields is not None:
        return
    _apply_translation(instance, [
        ('title_bs', 'title_en'),
        ('description_bs', 'description_en'),
        ('alt_text_bs', 'alt_text_en'),
        ('caption_bs', 'caption_en'),
    ])


@receiver(post_save, sender='gallery.FieldNote')
def translate_field_note(sender, instance, update_fields, **kwargs):
    if update_fields is not None:
        return
    # Only excerpt_en is blank=True and can be auto-translated.
    # title_en and body_en are required by the model (no blank=True) and must
    # be provided manually by the admin. Auto-translation for those fields
    # requires a schema migration to make them optional.
    _apply_translation(instance, [
        ('excerpt_bs', 'excerpt_en'),
    ])
