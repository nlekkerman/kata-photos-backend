# Gallery Album Cover API — Phase 5 Implementation Report

**Date:** 2026-06-01  
**Repository:** `kata-photos-backend`  
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)  
**Prerequisite:** Phase 4 — `documents/backend-docs/gallery-media-upload-api-phase-4-implementation-report-2026-06-01.md`

---

## Summary

Phase 5 adds a single protected endpoint for staff/admin users to set or clear an album's cover media. Public read endpoints are unchanged. Existing album and media write APIs from Phases 3–4 are unchanged. No frontend files were touched.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `AlbumCoverWriteSerializer` |
| `gallery/views.py` | Added `Response` import, `AlbumCoverWriteSerializer` import, `AlbumCoverUpdateView` |
| `gallery/urls.py` | Added `AlbumCoverUpdateView` import and URL pattern |
| `gallery/tests.py` | Added `AlbumCoverAPITests` (8 tests) |

**Total files changed: 4** (within the 1–5 target)  
**No migrations created.** Phase 5 is serializer/view-only — no model changes.

---

## Endpoint Added

| Method | URL | Auth required | Description |
|---|---|---|---|
| `PATCH` | `/api/gallery/albums/<slug>/cover/` | Staff/admin only | Set or clear album cover media |

### Accepted JSON body

**Set cover:**
```json
{ "cover_media_id": 123 }
```

**Clear cover:**
```json
{ "cover_media_id": null }
```

### Response

On success (`200 OK`): full album detail object using `AlbumDetailSerializer`, including updated `cover` field.

### Existing endpoints — unchanged behavior

| Method | URL | Auth | Description |
|---|---|---|---|
| `GET` | `/api/gallery/albums/` | Public | List published albums |
| `GET` | `/api/gallery/albums/<slug>/` | Public | Published album detail |
| `GET` | `/api/gallery/albums/<slug>/media/` | Public | Published media for published album |
| `GET` | `/api/gallery/media/<pk>/` | Public | Published media item |
| `POST` | `/api/gallery/albums/` | Staff/admin | Create album |
| `PATCH` | `/api/gallery/albums/<slug>/` | Staff/admin | Update album |
| `DELETE` | `/api/gallery/albums/<slug>/` | Staff/admin | Delete album |
| `POST` | `/api/gallery/albums/<slug>/media/` | Staff/admin | Upload media to album |
| `PATCH` | `/api/gallery/media/<pk>/` | Staff/admin | Update media metadata |
| `DELETE` | `/api/gallery/media/<pk>/` | Staff/admin | Delete media item |

---

## Serializer: `AlbumCoverWriteSerializer`

A plain `Serializer` (not a `ModelSerializer`) with a single field.

### Accepted input field

| Field | Type | Required | Notes |
|---|---|---|---|
| `cover_media_id` | integer or null | Yes | ID of a `MediaItem`, or `null` to clear |

### Validation rules (enforced in `validate()`)

1. If `cover_media_id` is `null` → clear cover, no further checks.
2. `cover_media_id` must reference an existing `MediaItem` → `400` if not found.
3. The `MediaItem` must belong to the same album (matched via URL slug) → `400` if from another album.
4. The `MediaItem.media_type` must be `'image'` → `400` if not.
5. The `MediaItem.is_published` must be `True` → `400` to prevent an unpublished draft from becoming the public cover.

All validation errors are returned as field-keyed dicts under `cover_media_id`.

### `save()` behavior

Sets `album.cover_media` to the validated `MediaItem` (or `None` to clear) and calls `album.save(update_fields=['cover_media'])`.

### Fields intentionally excluded

All album write fields (`title_bs`, `slug`, `is_published`, etc.) are excluded. The serializer is a focused single-purpose tool.

---

## View: `AlbumCoverUpdateView`

Inherits `LangContextMixin` and `generics.GenericAPIView`.

```
PATCH → IsAdminUser → AlbumCoverWriteSerializer → any album (published or not)
```

- `permission_classes = [IsAdminUser]` — enforces `is_staff=True` globally.
- `http_method_names = ['patch', 'head', 'options']` — `PUT` and `GET` are not routed.
- Album is looked up by slug from the URL. Returns `404` if the album does not exist.
- On success, returns `200 OK` with the album detail using `AlbumDetailSerializer`.
- The `lang` query param is respected in the response (via `LangContextMixin`).

---

## Permission Behavior

| User type | PATCH `/cover/` |
|---|---|
| Anonymous | 403 |
| Authenticated non-staff | 403 |
| Staff / admin | ✓ any album |

DRF's built-in `IsAdminUser` (`user.is_staff`) is used. Session-based authentication only.

Staff users may set or clear cover on unpublished albums. However, the media item itself must be published.

---

## Validation Behavior

| Input | Response |
|---|---|
| Valid published image from same album | `200 OK` + album detail |
| `cover_media_id: null` | `200 OK` + album detail (cover cleared) |
| Non-existent media ID | `400` `{'cover_media_id': 'Media item N not found.'}` |
| Media from another album | `400` `{'cover_media_id': 'Media item does not belong to this album.'}` |
| Unpublished media | `400` `{'cover_media_id': 'Cover media must be published.'}` |
| Non-image media type | `400` `{'cover_media_id': 'Cover media must be an image.'}` |
| Missing `cover_media_id` field | `400` (DRF required field error) |

---

## Tests Added

File: `gallery/tests.py`  
Class: `AlbumCoverAPITests` (8 tests)  
No `@override_settings(MEDIA_ROOT=...)` needed — tests create `MediaItem` rows directly without file uploads.

| Test | Assertion |
|---|---|
| `test_anonymous_cannot_set_cover` | PATCH without auth → 401 or 403 |
| `test_non_staff_cannot_set_cover` | PATCH as regular user → 401 or 403 |
| `test_staff_can_set_cover_to_published_image` | PATCH as staff → 200, `album.cover_media_id` updated |
| `test_staff_cannot_set_cover_to_media_from_another_album` | PATCH with cross-album media → 400, `cover_media_id` in errors |
| `test_staff_cannot_set_cover_to_unpublished_media` | PATCH with unpublished media → 400, `cover_media_id` in errors |
| `test_staff_can_clear_cover` | PATCH with `null` → 200, `album.cover_media` is None |
| `test_public_album_detail_includes_cover_after_set` | GET album detail → `cover.id` matches set media |
| `test_public_album_list_includes_cover_after_set` | GET album list → `cover.id` matches set media |

---

## Commands Run and Results

```
python manage.py makemigrations --check --dry-run
```
→ `No changes detected` (exit 0). Phase 5 is serializer/view-only.

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
→ `Ran 27 tests in 25.143s OK` — all 27 tests passed (8 Phase 3 + 11 Phase 4 + 8 Phase 5).

---

## Confirmation

- **No frontend files were touched.**
- **No media upload behavior was broken.** All 11 Phase 4 media upload tests continue to pass.
- **No album write behavior was broken.** All 8 Phase 3 album write tests continue to pass.
- **No translation logic was added.**
- **No Cloudinary or Cloudflare logic was added.**
- **No thumbnail logic was added.**
- **No fake or dummy English content was generated.**
- **No broad refactor was performed.**
- **Existing public API behavior is stable and tested.**

---

## Risks and Follow-up Notes

1. **`IsAdminUser` requires `is_staff=True`.** Same constraint as Phases 3–4. Custom editor/photographer roles would require a custom permission class.

2. **Cover can be set on unpublished albums.** Staff may set a cover on an album that is not yet published. The cover data will only be visible publicly once the album itself is published.

3. **Cover media must be published.** If staff later unpublishes the cover image (via `PATCH /api/gallery/media/<pk>/`), the album's `cover_media` FK still points to it. The public `AlbumDetailSerializer` uses `MediaCoverSerializer` which does not filter by `is_published`, so an unpublished cover image's thumbnail and alt text would still appear in public album responses. Consider adding a published guard in `MediaCoverSerializer` or the album queryset if this becomes a concern.

4. **Old file is not deleted on cover replacement.** Clearing or replacing the cover only updates the FK — no file is deleted. Orphaned file cleanup is out of scope (same as Phase 4 note 4).

5. **No optimistic locking.** Concurrent PATCH requests to `/cover/` could race. Acceptable for the current MVP scope.

6. **`cover_media` from `AlbumWriteSerializer` is still absent.** The Phase 3 album write serializer does not expose `cover_media`. The dedicated Phase 5 cover endpoint is the only way to set/clear cover via the API.
