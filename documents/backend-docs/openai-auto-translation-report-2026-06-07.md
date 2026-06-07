# OpenAI Auto-Translation (Bosnian → English) — Implementation Report

**Date:** 2026-06-07  
**Scope:** Backend only (`kata-photos-backend`). No frontend files were changed.

---

## Summary

Implemented backend-only OpenAI auto-translation for Bosnian-first content.  
When an admin creates or updates content with a Bosnian field filled and the matching English field blank, the backend calls OpenAI, translates to English, and saves the English fields via a follow-up partial save.

Translation fires through Django `post_save` signals so it covers all write paths (Django admin and REST API) without touching `views.py`.

---

## Files Changed

| File | Change |
|---|---|
| `requirements.txt` | Added `openai` |
| `gallery/services/translation.py` | **New** — low-level OpenAI translation service |
| `gallery/signals.py` | **New** — `post_save` signal handlers for all content models |
| `gallery/apps.py` | Added `ready()` to register signals |
| `config/settings.py` | Added `OPENAI_API_KEY` and `OPENAI_TRANSLATION_MODEL` settings |
| `documents/backend-docs/openai-auto-translation-report-2026-06-07.md` | **This report** |

Total: 5 code files changed + this report.

---

## Dependency Changes

Added to `requirements.txt`:

```
openai
```

The official OpenAI Python SDK (v1.x). No version pin; follows the existing style of unpinned packages in this project (`dj-database-url`, `psycopg2-binary`, `gunicorn`).

Install locally:

```bash
pip install openai
```

On Heroku, Heroku will install it from `requirements.txt` on the next deploy.

---

## Environment Variables Used

| Variable | Required | Default | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes (for translation) | `""` | If absent, translation is skipped with a warning; saves proceed normally |
| `OPENAI_TRANSLATION_MODEL` | No | `gpt-4o-mini` | Override model if needed |

Set on Heroku:

```bash
heroku config:set OPENAI_API_KEY="paste-your-key-here" --app kata-wild-backend
```

---

## Models and Fields Affected

### VideoClip

| Bosnian field | → | English field |
|---|---|---|
| `title_bs` | → | `title_en` |
| `description_bs` | → | `description_en` |

### Album

| Bosnian field | → | English field |
|---|---|---|
| `title_bs` | → | `title_en` |
| `description_bs` | → | `description_en` |
| `seo_title_bs` | → | `seo_title_en` |
| `seo_description_bs` | → | `seo_description_en` |

### MediaItem

| Bosnian field | → | English field |
|---|---|---|
| `title_bs` | → | `title_en` |
| `description_bs` | → | `description_en` |
| `alt_text_bs` | → | `alt_text_en` |
| `caption_bs` | → | `caption_en` |

### FieldNote

| Bosnian field | → | English field |
|---|---|---|
| `excerpt_bs` | → | `excerpt_en` |

> **Note:** `FieldNote.title_en` and `FieldNote.body_en` are defined without `blank=True` in the model, making them required fields in the Django admin form. They cannot be auto-translated without a schema migration that makes them optional. Auto-translating `excerpt_en` (which is `blank=True`) is supported. See follow-up recommendations.

---

## Exact Trigger Points

Translation is triggered by a Django `post_save` signal on each model after any full save (`update_fields is None`).

Write paths covered:
- Django admin create / save
- REST API `VideoClip.objects.create()` in `AdminVideoDirectUploadView`
- REST API `serializer.save()` in all admin gallery/image/video API views

Partial saves (e.g. `video.save(update_fields=['status'])`) are intentionally skipped — `update_fields is not None` guard returns early.

---

## Anti-Recursion Guard

After translating, the service calls:

```python
instance.save(update_fields=updated_fields)
```

The signals all check `if update_fields is not None: return` at the top. This means the follow-up save that writes English fields never triggers translation again. No thread-locals, no flags, no recursion possible.

---

## Error Handling Behaviour

| Scenario | Result |
|---|---|
| `OPENAI_API_KEY` not set | Warning logged; Bosnian content saves normally; English fields stay blank |
| `openai` package not installed | Error logged; same graceful fallback |
| OpenAI request fails (timeout, HTTP error, network) | Error logged; same graceful fallback |
| OpenAI returns invalid JSON | Error logged; same graceful fallback |
| OpenAI returns partial response (missing keys) | Only valid translated keys are applied; missing keys stay blank |
| English field already has content | Not touched; `_needs_translation()` returns False |
| Bosnian field is empty or whitespace-only | Not sent to OpenAI; `_needs_translation()` returns False |

All errors are logged but never bubble up to the HTTP response. The save always succeeds regardless of translation status.

---

## Edge Cases Handled

- Empty Bosnian field — skipped by `_needs_translation()`
- Whitespace-only Bosnian field — `strip()` check in `_needs_translation()`
- English field already filled — not overwritten
- Very short title — translated normally (no minimum length)
- Long description / body — no server-side length cap; OpenAI limit applies
- Newlines, quotes, special characters — handled by `json.dumps` encoding
- Bosnian characters (`č`, `ć`, `ž`, `š`, `đ`) — `json.dumps(ensure_ascii=False)` preserves them
- Locations (Bihać, Una, Plješevica) — translation instruction says "Preserve names and places"
- Latin species names — translation instruction says "Preserve Latin species names"
- Missing API key — warning logged; graceful skip
- OpenAI timeout — caught by `except Exception` in service; graceful skip
- Invalid JSON response — caught by `json.JSONDecodeError`; graceful skip
- Partial response — only valid keys applied
- Recursive save loop — prevented by `update_fields is not None` guard
- Duplicate save during one request — signal fires once per `save()` call; partial saves skipped
- Admin editing only English field — Bosnian still blank → `_needs_translation()` returns False for those pairs
- Admin editing Bosnian field after English already exists — English not overwritten

---

## Validation Commands Run

```bash
python manage.py check
```

Output: `System check identified no issues (0 silenced).`

---

## Manual Verification Checklist

1. **Create a VideoClip** with `title_bs`/`description_bs` filled and English fields blank (via Django admin or `POST /api/gallery/admin/videos/direct-upload/`). Confirm `title_en` and `description_en` are populated after save.

2. **Create an Album** (image or video gallery) with Bosnian fields and blank English fields. Confirm English fields are populated.

3. **Update a MediaItem** (image) with `title_bs` set and `title_en` blank. Confirm `title_en` is auto-generated.

4. **Create a FieldNote** and fill `excerpt_bs` while leaving `excerpt_en` blank. Confirm `excerpt_en` is populated. (Note: `title_en` and `body_en` are required and must be filled manually.)

5. **Update content where English fields already exist.** Confirm no English fields are overwritten.

6. **Remove `OPENAI_API_KEY` from `.env`.** Create a VideoClip with Bosnian title. Confirm it saves normally and `title_en` stays blank. Confirm a warning log entry is present.

7. **Confirm public API** (`GET /api/gallery/...`) returns the saved English fields normally.

8. **Confirm no frontend files changed.**

---

## Full Test Suite

Intentionally skipped as directed. Only `python manage.py check` was run.

---

## Frontend Files Changed

None. This is a backend-only change.

---

## Follow-up Recommendations

1. **FieldNote `title_en` / `body_en` auto-translation** — requires a schema migration to add `blank=True` to both fields. Once optional, they can be included in the `translate_field_note` signal like the other models.

2. **Tag `name_en` auto-translation** — `name_bs` is required and `name_en` is `blank=True`. The same signal pattern would work. Not implemented here to keep scope minimal.

3. **Translation on Bosnian field update** — currently, if admin updates `title_bs` after `title_en` already exists, `title_en` is not updated (rule: never overwrite existing English). A future opt-in "re-translate" admin action could handle this case.

4. **Async translation** — currently synchronous in the HTTP request. For very long bodies, consider Celery/background task to avoid holding up the save response.

5. **Model** — `gpt-4o-mini` is the default. Upgrade to `gpt-4o` or another model via `OPENAI_TRANSLATION_MODEL` if quality is insufficient for SEO-critical fields.
