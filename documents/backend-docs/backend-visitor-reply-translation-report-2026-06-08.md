# Backend: Visitor Reply Translation — Implementation Report

**Date:** 2026-06-08  
**Scope:** Backend only (`kata-photos-backend`)  
**Files changed:** 5

---

## Files Changed

| File | Change |
|------|--------|
| `gallery/services/translation.py` | Added `detect_language()` and `translate_bs_to_language()` |
| `gallery/services/visitor_reply.py` | **New file** — `prepare_visitor_reply_for_email()` helper |
| `gallery/models.py` | Added 7 translation audit fields to `VisitorMessageReply` |
| `gallery/migrations/0018_visitor_message_reply_translation_fields.py` | **New migration** for those fields |
| `gallery/views.py` | Wired helper into `VisitorMessageReplyView.post()` |

No frontend files were touched.

---

## Existing Translation Service Reused

`gallery/services/translation.py` already contained two OpenAI helpers:

- `translate_bs_to_en_fields()` — Bosnian → English field batch translation
- `translate_texts_to_bosnian()` — any language → Bosnian (for admin review)

Two new functions were added to the same module rather than creating a new OpenAI client:

- `detect_language(text)` — calls OpenAI with `response_format={"type": "json_object"}`, returns a lowercase BCP 47 code (`'bs'`, `'en'`, `'de'`, …) or `'unknown'` on any failure.
- `translate_bs_to_language(text, target_language)` — translates a Bosnian string into an arbitrary target language; returns `(translated_text, error_message)`.

Both functions reuse `settings.OPENAI_API_KEY` and `settings.OPENAI_TRANSLATION_MODEL` exactly as the existing helpers do. No duplicate `OpenAI` client is created at module level.

---

## Migration Added

`0018_visitor_message_reply_translation_fields.py` — depends on `0017_visitor_message_comment_translation_fields`.

Seven nullable/blank fields added to `VisitorMessageReply`:

| Field | Type | Purpose |
|-------|------|---------|
| `original_reply_body` | `TextField(blank=True)` | What Kata/admin wrote |
| `sent_reply_body` | `TextField(blank=True)` | What was actually emailed |
| `visitor_language` | `CharField(max_length=16, blank=True)` | Detected language of visitor message |
| `reply_language` | `CharField(max_length=16, blank=True)` | Detected language of admin reply |
| `translation_applied` | `BooleanField(default=False)` | True if Bosnian reply was translated |
| `translation_skipped_reason` | `CharField(max_length=120, blank=True)` | Why translation was skipped |
| `translation_error` | `TextField(blank=True)` | Error message if translation failed |

---

## Translation Decision Logic

Implemented in `gallery/services/visitor_reply.py` as `prepare_visitor_reply_for_email(visitor_message, admin_reply_body) -> PreparedVisitorReply`.

```
visitor_language = detect_language(visitor_message.message)
reply_language   = detect_language(admin_reply_body)

if visitor_language == 'unknown':
    send as-is
    translation_skipped_reason = 'visitor_language_unknown'

elif visitor_language == 'bs':
    send as-is
    translation_skipped_reason = 'visitor_language_is_bosnian'

elif reply_language == visitor_language:
    send as-is
    translation_skipped_reason = 'languages_already_match'

elif reply_language == 'bs':
    translated_body = translate_bs_to_language(admin_reply_body, visitor_language)
    if translation succeeded:
        send translated body
        translation_applied = True
    else:
        send original admin reply body
        translation_error = <error message>

else:
    send as-is
    translation_skipped_reason = 'reply_language_<X>_not_bosnian_and_not_visitor_language'
```

---

## Language Detection

`detect_language(text)` in `gallery/services/translation.py`:

- Sends the first 1 000 characters of the text to OpenAI with `temperature=0.0` and `response_format={"type": "json_object"}`.
- The model is asked to return `{"language_code": "<bcp47>"}`.
- Returns a lowercase BCP 47 code.
- Handles: missing API key, `openai` import error, network/timeout error, `json.JSONDecodeError`, missing/null/empty `language_code` key — all return `'unknown'`.
- Recognises at least: `bs`, `en`, `de`, `fr`, `it`, `es`, `hr`, `sr`, `sl`, `nl`, `pl`, `cs`, `sk`, `hu`, `ro`, `pt`, `ru`, `tr`, `ar`, `zh`, `ja`, `ko`, `sv`, `da`, `fi`, `nb`, `el` — unknown codes are accepted with a warning log, not rejected.

---

## Admin Reply Language Detection

Same `detect_language()` function applied to `admin_reply_body`. If the reply text is empty, `'unknown'` is returned immediately without an API call.

---

## Email Body Selection

`VisitorMessageReplyView.post()` calls `prepare_visitor_reply_for_email()` before building the email. The email body uses `prepared.body_to_send`:

- Translated body if `translation_applied = True`
- Original admin reply body if translation was skipped or failed

The quoted original visitor message is appended after `prepared.body_to_send` unchanged, as before.

---

## Failure Behaviour

- Translation failure does **not** crash the endpoint.
- The original `admin_reply_body` is sent.
- `translation_error` is saved on the `VisitorMessageReply` record.
- A `logger.error` entry is written.
- `translation_applied` remains `False`.

---

## Edge Cases Handled

| Case | Behaviour |
|------|-----------|
| Empty visitor message body | `detect_language` returns `'unknown'`; reply sent as-is |
| Empty admin reply body | `detect_language` returns `'unknown'`; reply sent as-is |
| Visitor language unknown | Sent as-is; reason saved |
| Visitor language is Bosnian | Sent as-is; reason saved |
| Reply language matches visitor language | Sent as-is; reason saved |
| Reply is Bosnian, visitor is not | Translation attempted |
| Reply not Bosnian, not visitor language | Sent as-is; reason saved |
| Translation API failure / timeout | Original sent; error saved |
| OpenAI API key missing | Translation skipped (`'unknown'` returned); original sent |
| `openai` package not installed | Translation skipped; original sent |
| OpenAI returns invalid JSON | `'unknown'`; original sent |
| OpenAI returns malformed language code | Accepted with warning log |
| Translation returns empty content | Treated as failure; original sent |
| Names, places, URLs, dates in reply | Preserved — system prompt instructs model to keep them |
| Line breaks | `\n` in reply body preserved; OpenAI instructed to keep them |
| Visitor email missing | Blocked by existing `if not message.sender_email` guard (unchanged) |

---

## Validation

```
python manage.py check
# → System check identified no issues (0 silenced).
```

Targeted gallery tests (100 tests including `VisitorMessageReplyViewTests`):

```
.\.venv\Scripts\python.exe manage.py test gallery.tests
# → Ran 100 tests in 32.873s — OK
```

`manage.py check` passed. All 100 pre-existing gallery tests pass.

---

## Confirmation

- No frontend files were touched.
- No duplicate OpenAI clients added.
- No mock/fake translation behaviour.
- No fallback legacy endpoints.
- No broad refactors.
- 5 files changed (within the 1–8 file cap).
