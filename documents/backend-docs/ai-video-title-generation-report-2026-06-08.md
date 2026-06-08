# Backend: AI-Generate Short SEO-Aware Video Titles — Implementation Report

**Date:** 2026-06-08  
**Scope:** Backend only (`kata-photos-backend`)  
**Full test suite:** Intentionally skipped per spec. Targeted tests only.

---

## Summary

When an admin uploads a video without a title, the backend now automatically generates a short, SEO-aware Bosnian title from `description_bs` using OpenAI, then generates/translates an English title from the resolved Bosnian title. If OpenAI is unavailable or fails, safe local fallbacks are used and the upload always succeeds.

---

## Files Changed

### New Files

| File | Purpose |
|---|---|
| `gallery/services/video_titles.py` | New service: AI Bosnian title generation + title resolution logic |
| `gallery/tests/test_video_title_generation.py` | 19 targeted tests for the new feature |

### Modified Files

| File | Change |
|---|---|
| `gallery/views.py` | Both video upload views wired to call `resolve_video_titles` and pass `meta={"name": title_bs}` to Cloudflare Stream |

---

## Detailed Changes

### `gallery/services/video_titles.py` (new)

Contains two public functions:

#### `generate_video_title_bs_from_description(description_bs: str) -> str | None`

- Calls OpenAI (`gpt-4o-mini` by default, respects `OPENAI_TRANSLATION_MODEL` setting).
- Uses a strict Bosnian-language system prompt instructing the model to return **only** `{"title_bs": "..."}` JSON.
- Prompt rules enforced: 3–5 words, SEO-natural, animal + location when both present, no clickbait, no invented facts, no hashtags, no trailing punctuation, preserve `č ć ž š đ`.
- Temperature: `0.3`, timeout: `20s`.
- Returns `None` (never raises) on: missing API key, missing `openai` package, network/API error, invalid JSON response, empty title in response.

#### `resolve_video_titles(*, title_bs, title_en, description_bs, original_filename, now) -> tuple[str, str]`

Resolves `(final_title_bs, final_title_en)` safe for `VideoClip` creation. Never raises. Always returns two non-blank strings.

**`title_bs` resolution order:**
1. Use `title_bs` if provided and non-blank (after `.strip()`).
2. Generate via `generate_video_title_bs_from_description(description_bs)`.
3. Local fallback: first sentence/chunk from `description_bs` (up to 60 chars).
4. Local fallback: cleaned filename — removes extension, replaces `_`/`-`/`.` with spaces.
5. Local fallback: timestamp string `"Video upload YYYY-MM-DD HH:MM"`.

**`title_en` resolution order:**
1. Use `title_en` if provided and non-blank.
2. Call existing `translate_bs_to_en_fields({"title_bs": final_bs})` — reuses the existing OpenAI translation service without duplication.
3. Fallback to `final_bs` if translation returns empty.

---

### `gallery/views.py` (modified)

Two upload views were updated identically:

- **`VideoClipDirectUploadView.post`** (line ~229) — legacy staff upload endpoint.
- **`AdminVideoDirectUploadView.post`** (line ~796) — admin panel upload endpoint.

**Before (both views):**
```python
cf_result = create_direct_upload(
    account_id=account_id,
    api_token=api_token,
    max_duration_seconds=data['max_duration_seconds'],
    expiry_seconds=expiry_seconds,
    watermark_uid=watermark_uid,
)
video = VideoClip.objects.create(
    ...
    title_bs=data['title_bs'],
    title_en=data.get('title_en', ''),
    ...
)
```

**After (both views):**
```python
from .services.video_titles import resolve_video_titles

title_bs, title_en = resolve_video_titles(
    title_bs=data.get('title_bs'),
    title_en=data.get('title_en'),
    description_bs=data.get('description_bs'),
)

cf_result = create_direct_upload(
    account_id=account_id,
    api_token=api_token,
    max_duration_seconds=data['max_duration_seconds'],
    expiry_seconds=expiry_seconds,
    watermark_uid=watermark_uid,
    meta={"name": title_bs},          # <-- Cloudflare meta.name now always set
)

video = VideoClip.objects.create(
    ...
    title_bs=title_bs,                # <-- resolved, never blank
    title_en=title_en,                # <-- resolved, never blank
    ...
)
```

**Cloudflare `meta.name`:** `create_direct_upload` already accepted an optional `meta` dict. `meta={"name": title_bs}` is now always passed. Because `resolve_video_titles` guarantees `title_bs` is non-blank, `meta.name` is never blank.

---

## Existing Code Reused

| Existing code | How reused |
|---|---|
| `gallery/services/translation.py` → `translate_bs_to_en_fields` | Imported directly in `resolve_video_titles` for `title_en` generation. No new OpenAI client setup. |
| `OPENAI_API_KEY` Django setting | Read via `getattr(settings, "OPENAI_API_KEY", "")` — same pattern as `translation.py`. |
| `OPENAI_TRANSLATION_MODEL` Django setting | Reused as model name for Bosnian title generation too. |
| Deferred `from openai import OpenAI` pattern | Same pattern as `translation.py` — import inside function body so `ImportError` is caught gracefully. |
| `create_direct_upload(meta=...)` param | Already supported in `cloudflare_stream.py`; no changes needed there. |

---

## Edge Cases Covered

| Edge case | Handling |
|---|---|
| `title_bs` provided and non-blank | Preserved as-is; AI is not called |
| `title_bs=None` | Treated as blank; AI generation attempted |
| `title_bs=""` | Treated as blank; AI generation attempted |
| `title_bs="   "` | `.strip()` → treated as blank; AI generation attempted |
| `description_bs=None` | Treated as blank; AI skipped; filename/timestamp fallback used |
| `description_bs=""` | Same as above |
| `description_bs="   "` | Same as above |
| OpenAI API key missing | `generate_video_title_bs_from_description` returns `None`; fallback chain continues |
| OpenAI request fails (network/timeout) | Exception caught; returns `None`; fallback chain continues |
| OpenAI returns invalid JSON | `json.JSONDecodeError` caught; returns `None` |
| OpenAI returns empty `title_bs` | Returns `None`; fallback chain continues |
| OpenAI returns title longer than expected | Accepted as-is (model is instructed to stay ≤5 words; no hard truncation to avoid cutting valid long location names) |
| Description has no animal/location | AI generates whatever it can; local fallback (first sentence) used if AI returns `None` |
| Bosnian special characters | Preserved; `ensure_ascii=False` used in JSON serialization; system prompt explicitly instructs model to preserve `č ć ž š đ` |
| `title_en` already provided | Preserved; translation not called |
| `title_en` blank | Translated from `final_title_bs` via `translate_bs_to_en_fields` |
| English translation fails | Falls back to `title_bs` |
| Cloudflare `meta.name` blank | Impossible — `resolve_video_titles` always returns non-blank `title_bs` |

---

## Validation

```
python manage.py check
→ System check identified no issues (0 silenced)

python manage.py test gallery.tests.test_video_title_generation --verbosity=2
→ Ran 19 tests in 1.437s — OK
```

---

## Tests Written (`gallery/tests/test_video_title_generation.py`)

### `GenerateTitleBsTests` (8 tests)

1. `test_generates_short_bosnian_title` — happy path, returns AI title
2. `test_preserves_animal_and_location_terms` — animal + location in output
3. `test_preserves_bosnian_characters` — `ć`, `š`, etc. survive
4. `test_returns_none_when_api_key_missing` — no key → `None`
5. `test_returns_none_when_description_blank` — blank/None/whitespace → `None`
6. `test_returns_none_on_invalid_json_response` — bad JSON → `None`
7. `test_returns_none_on_empty_title_in_response` — `{"title_bs": ""}` → `None`
8. `test_returns_none_on_openai_exception` — `RuntimeError` from OpenAI → `None`

### `ResolveVideoTitlesTests` (11 tests)

1. `test_provided_title_bs_is_preserved` — existing title not overwritten
2. `test_provided_title_en_is_preserved` — existing English title not overwritten
3. `test_whitespace_only_title_bs_is_treated_as_blank` — `"   "` → AI attempted
4. `test_blank_title_bs_generates_from_description` — `""` + description → AI title
5. `test_none_title_bs_generates_from_description` — `None` + description → AI title
6. `test_blank_title_en_is_generated_from_final_title_bs` — `translate_bs_to_en_fields` called
7. `test_title_en_fallback_to_title_bs_when_translation_fails` — translation empty → falls back to `title_bs`
8. `test_fallback_to_first_sentence_when_ai_fails` — AI raises → first sentence used
9. `test_fallback_to_filename_when_description_blank_and_ai_fails` — no description + AI raises → filename used
10. `test_fallback_to_timestamp_when_no_hints` — no title, no description, no filename, AI raises → timestamp
11. `test_cloudflare_meta_name_never_blank` — worst-case scenario still produces non-blank `title_bs`

---

## Confirmations

- **Backend only** — no frontend changes, no public API contract changes.
- **Upload never fails if OpenAI fails** — `resolve_video_titles` never raises; all OpenAI failure paths produce a local fallback title; `VideoClip.objects.create` always runs.
- **No duplication** — OpenAI client config and error handling are not duplicated; `translate_bs_to_en_fields` is imported and called directly.
- **No debug/temporary code** — no `print`, no mock data, no commented-out blocks left in production code.
