# Gallery Media Upload API — Phase 4 Implementation Report

**Date:** 2026-06-01  
**Repository:** `kata-photos-backend`  
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)  
**Prerequisite:** Phase 3 — `documents/backend-docs/gallery-album-write-api-phase-3-implementation-report-2026-06-01.md`

---

## Summary

Phase 4 adds protected media upload, update, and delete endpoints for staff/admin users. Public read endpoints are unchanged. Existing album write API from Phase 3 is unchanged. No frontend files were touched.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `MediaItemWriteSerializer` |
| `gallery/views.py` | Replaced `AlbumMediaListView` with `AlbumMediaListCreateView`; replaced `MediaItemDetailView` with `MediaItemRetrieveUpdateDestroyView`; added parser and serializer imports |
| `gallery/urls.py` | Updated imports to use new view names |
| `gallery/tests.py` | Added `MediaUploadAPITests` (11 tests); added `_make_image` helper and required imports |

**Total files changed: 4** (within the 1–5 target)  
**No migrations created.** Phase 4 is serializer/view-only — no model changes.

---

## Endpoints Added

| Method | URL | Auth required | Description |
|---|---|---|---|
| `POST` | `/api/gallery/albums/<slug>/media/` | Staff/admin only | Upload media to album |
| `PATCH` | `/api/gallery/media/<pk>/` | Staff/admin only | Partial update media metadata |
| `DELETE` | `/api/gallery/media/<pk>/` | Staff/admin only | Delete media item |

### Existing endpoints — unchanged behavior

| Method | URL | Auth | Description |
|---|---|---|---|
| `GET` | `/api/gallery/albums/` | Public | List published albums |
| `GET` | `/api/gallery/albums/<slug>/` | Public | Published album detail |
| `GET` | `/api/gallery/albums/<slug>/media/` | Public | Published media for published album |
| `GET` | `/api/gallery/media/<pk>/` | Public | Published media item (album must also be published) |

`PUT` is excluded on the detail endpoint (`http_method_names` excludes it). Only `PATCH` is supported for write operations.

---

## Serializer: `MediaItemWriteSerializer`

### Accepted input fields

| Field | Required | Notes |
|---|---|---|
| `original_file` | Yes (on create) | Image file — required via `validate()` |
| `media_type` | No | Default `image` |
| `title_bs` | No | |
| `caption_bs` | No | |
| `description_bs` | No | |
| `alt_text_bs` | No on draft; required if `is_published=True` | Enforced in `validate()` |
| `title_en` | No | |
| `caption_en` | No | |
| `description_en` | No | |
| `alt_text_en` | No | |
| `tags` | No | |
| `display_order` | No | |
| `is_published` | No | |

Read-only response fields: `id`, `width`, `height`, `file_size`, `created_at`, `updated_at`.

### Validation rules

1. **`original_file` required on create** — enforced in `validate()`. On PATCH (`partial=True`), `original_file` may be omitted.

2. **Published requires `alt_text_bs`** — if `is_published=True` and `alt_text_bs` is empty (considering existing instance value on partial update), returns `400 Bad Request` with `{'alt_text_bs': '...'}` error.

### Fields intentionally excluded from write serializer

- `album` — set from URL slug in `perform_create()`, not from request body
- `provider` — always set to `'local'` in `perform_create()`
- `provider_public_id`, `public_url`, `thumbnail_url` — not writable
- `duration_seconds` — not applicable to image uploads
- Legacy `title`, `alt_text`, `caption`, `description` fields — not exposed

---

## Permission Behavior

| User type | GET list/detail | POST create | PATCH update | DELETE |
|---|---|---|---|---|
| Anonymous | ✓ published only | 403 | 403 | 403 |
| Authenticated non-staff | ✓ published only | 403 | 403 | 403 |
| Staff / admin | ✓ published only | ✓ any album | ✓ any media | ✓ any media |

DRF's built-in `IsAdminUser` (`user.is_staff`) is used throughout. Session-based authentication only. No JWT or token auth added.

Staff users may upload to unpublished albums and may PATCH/DELETE unpublished media.

---

## Parser / Upload Behavior

`parser_classes = [MultiPartParser, FormParser, JSONParser]` is set explicitly on both `AlbumMediaListCreateView` and `MediaItemRetrieveUpdateDestroyView`. This keeps the change local to the write views and makes the intent explicit.

- `POST /api/gallery/albums/<slug>/media/` — accepts `multipart/form-data` with `original_file` as a file field.
- `PATCH /api/gallery/media/<pk>/` — accepts `multipart/form-data` (for file replacement) or `application/json` (for metadata-only update).

Width, height, and file size are populated by the existing `MediaItem.save()` → `_populate_local_image_metadata()` mechanism. No thumbnail generation is performed.

The `album` is resolved from the URL slug in `perform_create()`. The request body cannot specify a different album.

Newly uploaded media defaults to `is_published=False` (model default). It will not appear in public API responses until explicitly published via `PATCH`.

---

## View Implementation

### `AlbumMediaListCreateView`

Replaces `AlbumMediaListView`. Inherits `LangContextMixin` for GET lang resolution.

```
GET  → AllowAny  → MediaItemPublicSerializer  → published album + published media only
POST → IsAdminUser → MediaItemWriteSerializer → any album; album set from URL slug
```

- `get_queryset()` enforces `is_published=True` on both album and media for GET.
- `perform_create()` looks up album by slug (any published state), sets `album` and `provider='local'` on the created instance.
- Returns 404 if album slug does not exist (for either GET or POST).

### `MediaItemRetrieveUpdateDestroyView`

Replaces `MediaItemDetailView`. Inherits `LangContextMixin` for GET lang resolution.

```
GET    → AllowAny  → MediaItemPublicSerializer → published media + published album
PATCH  → IsAdminUser → MediaItemWriteSerializer → any media (partial=True handled by DRF)
DELETE → IsAdminUser → —                        → any media
```

`http_method_names` excludes `'put'` — only `PATCH` is supported for updates.

---

## Tests Added

File: `gallery/tests.py`  
Helper: `_make_image(name, size)` — creates a small in-memory JPEG using Pillow  
Class: `MediaUploadAPITests` (11 tests)  
Decorator: `@override_settings(MEDIA_ROOT=_TEMP_MEDIA)` — writes test uploads to a temporary directory cleaned up in `tearDownClass`

| Test | Assertion |
|---|---|
| `test_anonymous_cannot_upload_media` | POST without auth → 401 or 403 |
| `test_non_staff_cannot_upload_media` | POST as regular user → 401 or 403 |
| `test_staff_can_upload_image_to_album` | POST as staff → 201, MediaItem created |
| `test_uploaded_media_attached_to_album` | Created item's album matches URL album |
| `test_uploaded_media_defaults_to_unpublished` | `is_published=False` on new upload |
| `test_width_height_file_size_populated` | width, height, file_size set by `save()` |
| `test_published_without_alt_text_bs_rejected` | POST `is_published=True, alt_text_bs=''` → 400, `alt_text_bs` in errors |
| `test_public_list_excludes_unpublished_media` | GET → unpublished media not visible |
| `test_public_list_includes_published_media` | GET → published media visible |
| `test_staff_can_patch_media_metadata` | PATCH → 200, field updated |
| `test_staff_can_delete_media` | DELETE → 204, item removed from DB |

---

## Commands Run and Results

```
python manage.py makemigrations --check --dry-run
```
→ `No changes detected` (exit 0). Phase 4 is serializer/view-only.

```
python manage.py migrate
```
→ `No migrations to apply.`

```
python manage.py check
```
→ `System check identified no issues (0 silenced).`

```
python manage.py test --verbosity=2
```
→ `Ran 19 tests in 17.475s OK` — all 19 tests passed (8 Phase 3 + 11 Phase 4).

---

## What Was Intentionally Not Changed

| Area | Reason |
|---|---|
| `MediaItem` model | No changes needed — `save()` already populates width/height/file_size |
| Album write endpoints | Out of scope for Phase 4 |
| `FieldNote` views | Out of scope |
| JWT / token auth | Out of scope |
| Cloudinary / Cloudflare | Out of scope |
| Thumbnail generation | Out of scope |
| Translation logic | Out of scope |
| `config/settings.py` | No global DRF settings changed |
| Global DRF parser defaults | Parser classes set locally on write views only |
| `AlbumWriteSerializer` | Unchanged |
| Public serializers | Unchanged |

---

## Confirmation

- **No frontend files were touched.**
- **No album write behavior was broken.** All 8 Phase 3 album write tests continue to pass.
- **No translation logic was added.**
- **No Cloudinary or Cloudflare logic was added.**
- **No thumbnail logic was added.**
- **No fake or dummy English content was generated.**
- **No broad refactor was performed.**
- **Existing public API behavior is stable and tested.**

---

## Risks and Follow-up Notes

1. **`IsAdminUser` requires `is_staff=True`.** Same constraint as Phase 3. Custom editor/photographer roles would require a custom permission class.

2. **Session authentication only.** Staff users calling write endpoints from outside the Django admin session need CSRF tokens for unsafe methods. A future token auth system would address this.

3. **No file type enforcement beyond Pillow validation.** `ImageField` relies on Pillow to reject non-image files. Extremely large uploads are not rate-limited. Consider adding `MAX_UPLOAD_SIZE` validation for production.

4. **`original_file` can be replaced on PATCH.** A PATCH request that includes `original_file` will replace the existing file. The old file is not deleted from disk (Django's default behavior). Orphaned files require periodic cleanup or a `post_delete` signal.

5. **Uploaded media to unpublished albums.** Staff can POST media to an unpublished album. The media will not appear in any public endpoint until the album itself is published.

6. **Test media files.** `@override_settings(MEDIA_ROOT=_TEMP_MEDIA)` directs all test uploads to a temp directory that is cleaned up in `tearDownClass`. No test image fixtures are committed to the repository.

7. **`cover_media` on Album is still deferred.** Setting an album's cover image via the API remains a future phase item.
