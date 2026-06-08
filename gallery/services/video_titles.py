"""
AI-assisted video title resolution.

Exposes two public functions:

    generate_video_title_bs_from_description(description_bs) -> str | None
        Uses OpenAI to generate a short SEO-aware Bosnian title from a description.
        Returns None on any failure — missing key, network error, bad JSON, etc.

    resolve_video_titles(*, title_bs, title_en, description_bs, original_filename, now)
        -> tuple[str, str]
        Returns (final_title_bs, final_title_en) safe for VideoClip creation.
        Never raises; always returns non-blank strings.

Environment variables (via Django settings):
    OPENAI_API_KEY              — used by translate_bs_to_en_fields too
    OPENAI_TRANSLATION_MODEL    — optional; defaults to gpt-4o-mini
"""

import json
import logging
import re
from datetime import datetime, timezone

from django.conf import settings

from .translation import translate_bs_to_en_fields

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"

# Hard cap for AI-generated and fallback titles.
# Admin-provided titles are validated by the serializer (max_length=255) and are not capped here.
# 120 is generous enough for "animal + location" patterns while safely under the DB field limit.
_TITLE_MAX_LEN = 120

_TITLE_SYSTEM_PROMPT = (
    "Ti si stručnjak za SEO i bosanski jezik. "
    "Kada dobiješ opis video snimka s bosanskog, generiši kratak, prirodan naslov na bosanskom. "
    "Naslov mora biti: 3-5 riječi, SEO-prihvatljiv, bez klikbejta, bez izmišljenih činjenica, "
    "bez hashtaga, bez interpunkcije na kraju. "
    "Prednost daj kombinaciji: životinja + lokacija kada su oba prisutna. "
    "Sačuvaj bosanske karaktere: č, ć, ž, š, đ. "
    "Vrati SAMO validan JSON objekt oblika: {\"title_bs\": \"...\"}. "
    "Nikakav drugi tekst."
)


# ---------------------------------------------------------------------------
# Public: AI Bosnian title generation
# ---------------------------------------------------------------------------

def generate_video_title_bs_from_description(description_bs: str) -> str | None:
    """
    Use OpenAI to generate a short SEO-aware Bosnian video title from *description_bs*.

    Returns a non-blank string on success, None on any failure.
    Never raises.
    """
    if not description_bs or not description_bs.strip():
        return None

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY not configured; skipping AI Bosnian title generation."
        )
        return None

    model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") or _DEFAULT_MODEL

    user_prompt = (
        "Generiši kratak bosanski naslov za ovaj opis video snimka:\n\n"
        + description_bs.strip()
    )

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed; cannot generate Bosnian title.")
        return None

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            timeout=20,
        )
    except Exception as exc:
        logger.error("OpenAI Bosnian title generation request failed: %r", exc)
        return None

    try:
        content = response.choices[0].message.content
        parsed = json.loads(content)
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.error("OpenAI Bosnian title generation parse error: %r", exc)
        return None

    title = parsed.get("title_bs")
    if not isinstance(title, str) or not title.strip():
        logger.warning("OpenAI returned empty or invalid title_bs: %r", parsed)
        return None

    return title.strip()[:_TITLE_MAX_LEN]


# ---------------------------------------------------------------------------
# Internal: local fallbacks
# ---------------------------------------------------------------------------

def _first_sentence_from_description(description_bs: str) -> str:
    """Extract the first non-blank sentence or short chunk from a description."""
    text = description_bs.strip()
    # Split on sentence-ending punctuation; take first non-empty part
    parts = re.split(r'[.!?]\s+', text)
    for part in parts:
        chunk = part.strip()
        if chunk:
            # Truncate to 60 chars to stay title-like
            return chunk[:60]
    # Fallback: first 60 chars of the raw description
    return text[:60]


def _clean_filename(original_filename: str) -> str:
    """Return a human-readable title derived from a filename (without extension)."""
    base = re.sub(r'\.[^.]+$', '', original_filename).strip()
    # Replace underscores/hyphens/dots with spaces
    base = re.sub(r'[_\-\.]+', ' ', base).strip()
    return base[:80] if base else ""


# ---------------------------------------------------------------------------
# Public: title resolution
# ---------------------------------------------------------------------------

def resolve_video_titles(
    *,
    title_bs: str | None,
    title_en: str | None,
    description_bs: str | None,
    original_filename: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """
    Resolve safe (title_bs, title_en) for VideoClip creation.

    Strategy:
    1. Use title_bs if non-blank.
    2. Generate title_bs via OpenAI from description_bs.
    3. Local fallbacks: first sentence of description_bs, cleaned filename,
       timestamp string.

    For title_en:
    1. Use title_en if non-blank.
    2. Translate final title_bs via existing translate_bs_to_en_fields.
    3. Fallback to title_bs.

    Never raises; always returns two non-blank strings.
    """
    # ---- Resolve title_bs --------------------------------------------------
    bs_input = (title_bs or "").strip()
    if bs_input:
        final_bs = bs_input
    else:
        # Try AI generation
        desc = (description_bs or "").strip()
        final_bs = generate_video_title_bs_from_description(desc) or ""

        if not final_bs and desc:
            # Local fallback 1: first sentence/chunk from description
            final_bs = _first_sentence_from_description(desc)

        if not final_bs and original_filename:
            # Local fallback 2: cleaned filename
            final_bs = _clean_filename(original_filename)

        if not final_bs:
            # Local fallback 3: timestamp
            ts = now or datetime.now(tz=timezone.utc)
            final_bs = ts.strftime("Video upload %Y-%m-%d %H:%M")

    # ---- Resolve title_en --------------------------------------------------
    en_input = (title_en or "").strip()
    if en_input:
        final_en = en_input
    else:
        translated = translate_bs_to_en_fields({"title_bs": final_bs})
        final_en = translated.get("title_bs", "").strip() or final_bs

    return final_bs, final_en
