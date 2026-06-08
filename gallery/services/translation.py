"""
OpenAI translation service: Bosnian → English.

Exposes a single function:

    translate_bs_to_en_fields(fields: dict) -> dict

Environment variables (consumed via Django settings):
    OPENAI_API_KEY              — required; translation skipped with warning if absent.
    OPENAI_TRANSLATION_MODEL    — optional; defaults to gpt-4o-mini.

The caller is responsible for only passing fields where translation is needed
(Bosnian has content, English is blank). This module never writes to the database.
"""

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_INSTRUCTION = (
    "Translate the provided Bosnian wildlife/photography website content into natural English. "
    "Do not add facts. Do not rewrite as marketing copy. "
    "Preserve names, places, dates, Latin species names, and meaning. "
    "Keep the output human and simple. "
    "Return only valid JSON with the requested keys."
)


def translate_bs_to_en_fields(fields: dict) -> dict:
    """
    Translate a dict of Bosnian field values to English using OpenAI.

    Args:
        fields: {field_key: bosnian_text, ...}
                Only non-blank Bosnian fields that need translation should be passed.

    Returns:
        {field_key: english_text, ...}
        Only keys with a valid non-empty translated string are included.
        Returns an empty dict on any failure — API error, timeout, bad JSON, etc.
        Never raises.
    """
    if not fields:
        return {}

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not configured; skipping Bosnian→English auto-translation."
        )
        return {}

    model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") or _DEFAULT_MODEL

    user_prompt = (
        "Translate these Bosnian field values to English.\n"
        "Return a valid JSON object with exactly these keys: "
        + json.dumps(list(fields.keys()), ensure_ascii=False)
        + ".\n\nField values:\n"
        + json.dumps(fields, ensure_ascii=False)
    )

    try:
        from openai import OpenAI
    except ImportError:
        logger.error(
            "openai package is not installed; cannot auto-translate content."
        )
        return {}

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=30,
        )
    except Exception as exc:
        logger.error("OpenAI translation request failed: %r", exc)
        return {}

    try:
        content = response.choices[0].message.content
        translated = json.loads(content)
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.error(
            "OpenAI translation response parse error: %r",
            exc,
        )
        return {}

    # Only return clean string values for requested keys; ignore extra or null entries.
    result = {}
    for key in fields:
        value = translated.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()

    return result


# ---------------------------------------------------------------------------
# Visitor text → Bosnian translation (for admin review)
# ---------------------------------------------------------------------------

_VISITOR_TO_BOSNIAN_SYSTEM = (
    "Translate the following visitor-submitted text to natural Bosnian in Latin script. "
    "Preserve names, places, animal names, emails, phone numbers, URLs, timestamps, and technical details. "
    "Do not summarize. "
    "Do not add new meaning. "
    "Keep the tone close to the original. "
    "If the text is already Bosnian, return it unchanged or only lightly normalize obvious typos. "
    "Return only valid JSON with the requested keys."
)


def translate_texts_to_bosnian(fields: dict) -> tuple:
    """
    Translate a dict of visitor-submitted text values to Bosnian using OpenAI.

    Intended for VisitorMessage and VideoTimestampComment admin-review translations.
    Original text is never modified by this function; only translated values are returned.

    Args:
        fields: {field_key: source_text, ...}

    Returns:
        (translated_dict, status, error_message) where:
          - translated_dict: {field_key: bosnian_text} — only successfully translated keys
          - status: 'translated' | 'skipped' | 'failed'
          - error_message: short safe string, '' on success/skip
        Never raises.
    """
    if not fields:
        return ({}, 'skipped', '')

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not configured; skipping visitor text → Bosnian translation."
        )
        return ({}, 'skipped', '')

    model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") or _DEFAULT_MODEL

    user_prompt = (
        "Translate these visitor-submitted field values to natural Bosnian in Latin script.\n"
        "Return a valid JSON object with exactly these keys: "
        + json.dumps(list(fields.keys()), ensure_ascii=False)
        + ".\n\nField values:\n"
        + json.dumps(fields, ensure_ascii=False)
    )

    try:
        from openai import OpenAI
    except ImportError:
        logger.error(
            "openai package is not installed; cannot translate visitor text to Bosnian."
        )
        return ({}, 'failed', 'openai package not installed')

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _VISITOR_TO_BOSNIAN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=30,
        )
    except Exception as exc:
        logger.error("OpenAI visitor→Bosnian translation request failed: %r", exc)
        return ({}, 'failed', 'Translation request failed.')

    try:
        content = response.choices[0].message.content
        translated = json.loads(content)
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.error(
            "OpenAI visitor→Bosnian translation response parse error: %r", exc
        )
        return ({}, 'failed', 'Translation response parse error.')

    result = {}
    for key in fields:
        value = translated.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()

    if not result:
        return ({}, 'failed', 'Translation returned no usable content.')

    return (result, 'translated', '')


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_KNOWN_LANGUAGE_CODES = frozenset([
    'bs', 'en', 'de', 'fr', 'it', 'es', 'hr', 'sr', 'sl',
    'nl', 'pl', 'cs', 'sk', 'hu', 'ro', 'pt', 'ru', 'tr',
    'ar', 'zh', 'ja', 'ko', 'sv', 'da', 'fi', 'nb', 'el',
])


def detect_language(text: str) -> str:
    """
    Detect the language of ``text`` using OpenAI and return a BCP 47 language code.

    Returns:
        A lowercase BCP 47 language code such as 'bs', 'en', 'de', etc.
        Returns 'unknown' if detection fails, the API key is missing, or the
        response cannot be parsed.
        Never raises.
    """
    if not text or not text.strip():
        return 'unknown'

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY is not configured; cannot detect language.")
        return 'unknown'

    model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") or _DEFAULT_MODEL

    user_prompt = (
        "Detect the language of the following text. "
        "Return a JSON object with exactly one key: \"language_code\". "
        "The value must be a lowercase BCP 47 language code such as "
        "\"bs\", \"en\", \"de\", \"fr\", \"hr\", \"sr\", \"sl\", \"it\", \"es\", etc. "
        "If you cannot determine the language confidently, return {\"language_code\": \"unknown\"}. "
        "Do not return anything except the JSON object.\n\n"
        "Text:\n"
        + text[:1000]
    )

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package is not installed; cannot detect language.")
        return 'unknown'

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a language detection assistant. Respond only with valid JSON."},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=20,
        )
    except Exception as exc:
        logger.error("OpenAI language detection request failed: %r", exc)
        return 'unknown'

    try:
        content = response.choices[0].message.content
        result = json.loads(content)
        code = result.get("language_code", "")
        if isinstance(code, str):
            code = code.strip().lower()
            if code and code != 'unknown':
                # Normalize region variants to base language (e.g. 'en-us' → 'en').
                if '-' in code:
                    code = code.split('-')[0]
                # Validate: must be 2–3 lowercase ASCII letters only.
                if not re.fullmatch(r'[a-z]{2,3}', code):
                    logger.warning(
                        "Language detection returned malformed code %r; treating as unknown.",
                        code,
                    )
                    return 'unknown'
                return code
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.error("OpenAI language detection response parse error: %r", exc)

    return 'unknown'


# ---------------------------------------------------------------------------
# Generic Bosnian → target language translation (for admin reply emails)
# ---------------------------------------------------------------------------

_BS_TO_TARGET_SYSTEM = (
    "You are a professional translator. "
    "Translate the provided Bosnian text into the target language indicated by the user. "
    "Preserve names, places, animal names, emails, phone numbers, URLs, dates, and line breaks exactly. "
    "Do not add, summarise, or remove meaning. "
    "Keep the tone close to the original. "
    "Return only valid JSON with the requested keys."
)


def translate_bs_to_language(text: str, target_language: str) -> tuple:
    """
    Translate a Bosnian ``text`` into ``target_language`` using OpenAI.

    Args:
        text:            Bosnian source text.
        target_language: BCP 47 language code for the output language, e.g. 'en', 'de'.

    Returns:
        (translated_text, error_message) where:
          - translated_text: non-empty string on success, '' on failure.
          - error_message:   '' on success, short safe description on failure.
        Never raises.
    """
    if not text or not text.strip():
        return ('', 'Source text is empty.')

    if not target_language or target_language in ('unknown', 'bs'):
        return ('', f'Translation to "{target_language}" not applicable.')

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY is not configured; skipping Bosnian→%s translation.", target_language)
        return ('', 'OPENAI_API_KEY not configured.')

    model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") or _DEFAULT_MODEL

    user_prompt = (
        f"Translate the following Bosnian text to {target_language}.\n"
        "Return a valid JSON object with exactly one key: \"translated\".\n\n"
        "Bosnian text:\n"
        + json.dumps(text, ensure_ascii=False)
    )

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package is not installed; cannot translate Bosnian→%s.", target_language)
        return ('', 'openai package not installed.')

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _BS_TO_TARGET_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=30,
        )
    except Exception as exc:
        logger.error("OpenAI Bosnian→%s translation request failed: %r", target_language, exc)
        return ('', 'Translation request failed.')

    try:
        content = response.choices[0].message.content
        result = json.loads(content)
        translated = result.get("translated", "")
        if isinstance(translated, str) and translated.strip():
            return (translated.strip(), '')
        return ('', 'Translation returned empty content.')
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.error("OpenAI Bosnian→%s translation response parse error: %r", target_language, exc)
        return ('', 'Translation response parse error.')
