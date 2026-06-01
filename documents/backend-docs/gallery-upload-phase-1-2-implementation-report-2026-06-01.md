# Gallery Upload Phase 1 & 2 — Implementation Report

**Date:** 2026-06-01  
**Repository:** `kata-photos-backend`  
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)  
**Source audit:** `documents/audits/gallery-upload-api-readiness-audit-2026-05-31.md`

---

## Summary

Phase 1 (Admin Bosnian-first fix) and Phase 2 (Image upload storage improvement) have been implemented and validated. No frontend files were touched. No API write endpoints were added.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/models.py` | `Album.title blank=True`; `Album.clean()` validation; `Album.__str__` Bosnian-first; `MediaItem.original_file` → `ImageField`; `MediaItem.__str__` Bosnian-first; `MediaItem.save()` + `_populate_local_image_metadata()` |
| `gallery/admin.py` | `AlbumAdmin`: added `prepopulated_fields`, reordered fieldsets Bosnian-first, updated `list_display`/`search_fields`/`ordering` |
| `requirements.txt` | Added `Pillow==11.2.1` |
| `gallery/migrations/0006_alter_album_title_alter_mediaitem_original_file.py` | Generated migration for the two field changes |

**Total files changed: 4** (within the 1–5 target)

---

## Phase 1 — Admin Bosnian-first fix

### 1. `Album.title` made optional (`blank=True`)

```python
title = models.CharField(max_length=200, blank=True)
```

The legacy `title` field no longer blocks form submission. Bosnian and English bilingual fields remain unchanged.

### 2. `Album.clean()` validation added

```python
def clean(self):
    if self.is_published and not self.title_bs:
        raise ValidationError({'title_bs': 'Naslov na bosanskom je obavezan za objavljene albume.'})
```

- Fires via Django's form validation (admin save).
- Only enforces `title_bs` for published albums.
- No English field required.
- Error message is in Bosnian.

### 3. `AlbumAdmin.prepopulated_fields`

```python
prepopulated_fields = {'slug': ('title_bs',)}
```

Slug is now auto-populated from `title_bs` in the admin form, matching the Bosnian-first policy.

### 4. Admin fieldsets reordered (Bosnian before English)

- `AlbumAdmin` fieldset order: Publishing → Bosnian Content → English Content → SEO Bosnian → SEO English → Timestamps  
- `list_display`, `search_fields`, `ordering` updated to prioritise `title_bs`.
- `MediaItemAdmin` fieldsets were already acceptable and were not changed (change would have been cosmetic-only and outside the scope of a small diff).

### 5. `__str__` updated to Bosnian-first

Both `Album.__str__` and `MediaItem.__str__` now prefer `title_bs` before `title_en` before legacy `title`.

---

## Phase 2 — Image upload storage improvement

### 1. Pillow added

Added to `requirements.txt`:
```
Pillow==11.2.1
```

Installed into the project virtualenv.

### 2. `MediaItem.original_file` changed to `ImageField`

```python
original_file = models.ImageField(upload_to='gallery/originals/', null=True, blank=True)
```

`ImageField` is a subclass of `FileField` that validates the uploaded file is a valid image (requires Pillow). All existing `upload_to`, `null`, and `blank` constraints preserved.

### 3. Migration created

`gallery/migrations/0006_alter_album_title_alter_mediaitem_original_file.py`

Contains two `AlterField` operations. Neither changes the database column type (both are varchar-backed); the migration is schema-tracking only and applies cleanly.

### 4. Image metadata population on save

`MediaItem.save()` calls `_populate_local_image_metadata()` when `provider == 'local'` and `original_file` is set.

**New upload path** (`_committed = False` — file not yet on disk):
- `file_size` ← `raw.size` (from `InMemoryUploadedFile` / `TemporaryUploadedFile`)
- `width`, `height` ← `PIL.Image.open(raw).size`
- File pointer is reset to 0 after reading so Django's storage backend can write it normally.

**Existing committed file path** (`_committed = True`):
- Only fills fields that are missing (does not overwrite already-populated values).
- `file_size` ← `os.path.getsize(path)`
- `width`, `height` ← `PIL.Image.open(path).size`

**Error handling:** Pillow `UnidentifiedImageError` and any other exceptions are caught silently — metadata is best-effort and the save always proceeds.

No thumbnails are generated. No Cloudinary or Cloudflare logic was added.

---

## Migrations Created

| Migration | Operations |
|---|---|
| `0006_alter_album_title_alter_mediaitem_original_file.py` | `AlterField(album.title, blank=True)` + `AlterField(mediaitem.original_file, ImageField)` |

---

## Commands Run and Results

```
python manage.py makemigrations --check --dry-run
```
→ Found 2 pending changes (Album.title, MediaItem.original_file). Exit code 1 as expected for `--check` (changes pending).

```
python manage.py makemigrations
```
→ Created `gallery/migrations/0006_alter_album_title_alter_mediaitem_original_file.py`. OK.

```
python manage.py migrate
```
→ `Applying gallery.0006_alter_album_title_alter_mediaitem_original_file... OK`

```
python manage.py check
```
→ `System check identified no issues (0 silenced).`

```
python manage.py test
```
→ `Ran 0 tests in 0.000s — NO TESTS RAN`. Exit code 1.  
No tests exist in the project (`gallery/tests.py` is a placeholder). This is a pre-existing condition, not a regression. No tests were broken.

---

## What Was Intentionally Not Changed

| Area | Reason |
|---|---|
| Public serializers (`gallery/serializers.py`) | No change required; public read API unaffected |
| Public read API views (`gallery/views.py`) | No write endpoints added |
| URL routing (`gallery/urls.py`) | No change |
| Django settings (`config/settings.py`) | No change |
| `MediaItemAdmin` fieldset order | Change would be cosmetic-only; kept diff small |
| JWT / session auth | Out of scope for Phase 1–2 |
| Cloudinary / Cloudflare logic | Out of scope for Phase 1–2 |
| Thumbnail generation | Out of scope for Phase 1–2 |
| Automatic translation | Not implemented; no fake English content added |

---

## Confirmation

- **No frontend files were touched.**
- **No API write endpoints were added.**
- **No fake/dummy content was introduced.**
- **No automatic translation was added.**
- **No Cloudinary or Cloudflare logic was added.**
- **No thumbnail generation was added.**

---

## Risks and Follow-up Notes

1. **`Album.title` still exists as a legacy field.** It is now optional (`blank=True`) but not removed. Downstream code that reads `album.title` without fallback will get an empty string if only `title_bs` is set. The `__str__` method now falls back correctly, but any serializer or template using `album.title` directly should be audited in a later phase.

2. **`Album.clean()` fires via Django form validation only.** It does not fire on programmatic `model.save()` calls (e.g. from management commands or fixtures). If write API endpoints are added later, the validation must be explicitly called or duplicated in serializer validation.

3. **`_populate_local_image_metadata()` is best-effort.** If Pillow cannot parse the image (e.g. a corrupt file uploaded through admin), width/height are silently left as `None`. The upload itself still succeeds. This is intentional.

4. **No write endpoint exists yet.** The metadata population in `save()` is exercised by the Django admin. When a public write API is added, the same `save()` hook will fire automatically — no additional wiring is needed.

5. **`ImageField` validates image format at the form layer.** Non-image files uploaded via admin will be rejected before reaching `save()`. Programmatic uploads bypassing the form layer will still be accepted by the model (same as `FileField` was before).
