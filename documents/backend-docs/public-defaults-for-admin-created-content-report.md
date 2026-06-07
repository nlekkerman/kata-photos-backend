# Public Defaults For Admin-Created Content Report

## Summary

All three models (`Album`, `MediaItem`, `VideoClip`) have `False` as their model-level default for their visibility field. No creation view or helper previously overrode these defaults, so every admin-created album, image, and video landed in a hidden state and never appeared on public pages without a manual PATCH to flip the flag.

Six targeted edits in `gallery/views.py` and three test assertion updates in `gallery/tests.py` fix this. Public endpoint filters are unchanged. No migrations required.

---

## Root Cause

| Model | Field | Model default (before) |
|---|---|---|
| `Album` | `is_published` | `False` |
| `MediaItem` | `is_published` | `False` |
| `VideoClip` | `is_public` | `False` |

Creation views called `serializer.save(...)` or `VideoClip.objects.create(...)` without passing the visibility field, so the model default of `False` was written to the DB silently.

---

## Files Changed

- `gallery/views.py` — 6 targeted edits across 4 sites
- `gallery/tests.py` — 3 assertion updates to match new behavior

---

## Creation Paths Inspected

| Model | Path | File / function | Previous default behavior | New behavior |
|---|---|---|---|---|
| `Album` | `POST /api/gallery/admin/image-galleries/` | `AdminImageGalleryListCreateView.perform_create` | `is_published=False` (model default) | `is_published=True` |
| `Album` | `POST /api/gallery/admin/video-galleries/` | `AdminVideoGalleryListCreateView.perform_create` | `is_published=False` (model default) | `is_published=True` |
| `Album` | `POST /api/gallery/albums/` (legacy) | `AlbumListCreateView` | `is_published=False` (model default) — **unchanged, see note** | unchanged |
| `MediaItem` | `POST /api/gallery/admin/images/` | `AdminImageItemListCreateView.perform_create` → `_save_media_item_with_cloudflare` | `is_published=False` (model default) | `is_published=True` |
| `MediaItem` | `POST /api/gallery/albums/<slug>/media/` | `AlbumMediaListCreateView.perform_create` → `_save_media_item_with_cloudflare` | `is_published=False` (model default) | `is_published=True` |
| `VideoClip` | `POST /api/gallery/admin/videos/direct-upload/` | `AdminVideoDirectUploadView.post` | `is_public=False` (explicit) | `is_public=True` |
| `VideoClip` | `POST /api/gallery/videos/direct-upload/` (legacy) | `VideoClipDirectUploadView.post` | `is_public=False` (explicit) | `is_public=True` |

**Note on legacy `AlbumListCreateView`**: this endpoint (`/api/gallery/albums/`) is still reachable and admin-gated, but is not changed in this patch. The frontend currently (incorrectly) uses this path when creating video galleries, so auto-publishing here would make that bug worse. The proper fix is a frontend refactor to use the typed admin endpoints. This is tracked as a separate task.

### `_save_media_item_with_cloudflare` — both code paths fixed

This shared helper is called by both `AlbumMediaListCreateView` and `AdminImageItemListCreateView`. It has two `serializer.save()` branches:

- **Local fallback** (no Cloudflare credentials or no file): `is_published=True` added
- **Cloudflare Images success path**: `is_published=True` added

Both fixed in one place.

### `AdminImageGalleryListCreateView` — `gallery_type` lock retained

`perform_create` already locked `gallery_type=Album.GALLERY_TYPE_IMAGE`. The update extends it:
```python
serializer.save(gallery_type=Album.GALLERY_TYPE_IMAGE, is_published=True)
```
The corresponding `perform_update` on `AdminImageGalleryRetrieveUpdateDestroyView` already locks `gallery_type` on PATCH — not changed.

Same pattern for `AdminVideoGalleryListCreateView`.

---

## Public Visibility Contract

Public endpoints are **unchanged**. Filters remain strict:

| Resource | Public filter |
|---|---|
| Albums | `is_published=True` |
| Images (album media) | album `is_published=True` + item `is_published=True` + `media_type='image'` |
| Videos (public list/detail) | `is_public=True` + `status='ready'` |
| Videos (album videos) | album `is_published=True` + `gallery_type='video'` + `is_public=True` + `status='ready'` |
| Hero video | `is_public=True` + `status='ready'` |

Videos with `is_public=True` and `status='uploading'` or `status='processing'` remain hidden from all public endpoints. A video only becomes publicly visible after `AdminVideoRefreshStatusView` syncs Cloudflare and sets `status='ready'`.

### Refresh-to-failed safety unchanged

`AdminVideoRefreshStatusView.post` (and `VideoClipSyncView.post`) still forces `is_public=False` whenever Cloudflare reports `status='failed'`:

```python
if new_status == VideoClip.STATUS_FAILED and video.is_public:
    video.is_public = False
    update_fields.append('is_public')
```

This is untouched.

### PATCH publish guard unchanged

`AdminVideoItemWriteSerializer.validate()` still blocks setting `is_public=True` via PATCH when `status != 'ready'`. This guard only fires on PATCH (uses `self.instance`). Direct `VideoClip.objects.create(...)` in the views bypasses this serializer — no conflict.

---

## Tests / Checks Run

**`python manage.py check`**: `System check identified no issues (0 silenced).`

**Targeted test execution**: blocked by a **pre-existing** test discovery conflict in the repo — `gallery/tests.py` (file) and `gallery/tests/` (package) shadow each other. Django's test runner raises `ImportError: 'tests' module incorrectly imported` when discovering the `gallery` app. This conflict exists before this patch and is unrelated to it.

Three test assertions were updated to reflect the new defaults. They are correct by inspection:

| Test | Class | File | Change |
|---|---|---|---|
| `test_uploaded_media_defaults_to_unpublished` | `MediaUploadAPITests` | `gallery/tests.py:133` | `assertFalse` → `assertTrue` |
| `test_direct_upload_creates_videoclip_record` (is_public assertion) | `VideoClipDirectUploadWatermarkTests` | `gallery/tests.py:414` | `assertFalse` → `assertTrue` |
| `test_admin_direct_upload_creates_video_with_is_public_false` | `AdminUploadLifecycleSafetyTests` | `gallery/tests.py:2590` | `assertFalse` → `assertTrue`; docstring updated |

All other assertions in `AdminUploadLifecycleSafetyTests` that test the complete-upload/refresh/PATCH-guard lifecycle remain correct and unchanged — they test transitions and guards, not the initial default.

---

## Edge Cases Covered

| Scenario | Result |
|---|---|
| New image gallery created via admin endpoint | `gallery_type='image'`, `is_published=True` |
| New video gallery created via admin endpoint | `gallery_type='video'`, `is_published=True` |
| Image uploaded to image gallery (Cloudflare path) | `MediaItem.is_published=True`, `media_type='image'` |
| Image uploaded to image gallery (local fallback path) | `MediaItem.is_published=True`, `media_type='image'` |
| Video direct upload initiated | `VideoClip.is_public=True`, `status='uploading'` — hidden from public |
| Video while processing | `status='processing'` — hidden from public |
| Video after refresh returns ready | `status='ready'` — appears publicly |
| Video refresh returns failed | `is_public` forced to `False`, `status='failed'` — hidden |
| PATCH attempts to publish non-ready video | Serializer validation rejects with 400 |
| Existing records | Not touched — no bulk update, no migration |
| Legacy `/api/gallery/albums/` POST | Unchanged — still creates with `is_published=False` |
| Image cannot attach to video gallery | Enforced at serializer level (`AdminImageItemWriteSerializer` restricts `album` queryset to `gallery_type='image'`) |
| Video cannot attach to image gallery | Enforced at serializer level (`AdminVideoItemWriteSerializer` restricts `album` queryset to `gallery_type='video'`) |
| Duplicate refresh calls | Only dirty fields are saved via `update_fields`; no unrelated records affected |

---

## Manual Verification Steps

1. Create image gallery: `POST /api/gallery/admin/image-galleries/` with `{"title_bs": "..."}`.
2. Confirm DB: `Album.gallery_type='image'`, `is_published=True`.
3. Upload image: `POST /api/gallery/admin/images/` with multipart file and `album=<pk>`.
4. Confirm DB: `MediaItem.is_published=True`, `media_type='image'`.
5. Confirm image appears at `GET /api/public/albums/<slug>/media/`.
6. Create video gallery: `POST /api/gallery/admin/video-galleries/` with `{"title_bs": "..."}`.
7. Confirm DB: `Album.gallery_type='video'`, `is_published=True`.
8. Initiate video upload: `POST /api/gallery/admin/videos/direct-upload/` with `{"title_bs": "...", "max_duration_seconds": 60, "album": <pk>}`.
9. Confirm DB: `VideoClip.is_public=True`, `status='uploading'`.
10. Confirm video does NOT appear at `GET /api/public/videos/` or `GET /api/public/albums/<slug>/videos/` while `status != 'ready'`.
11. Complete upload: `POST /api/gallery/admin/videos/complete-upload/` with `{"video_id": <pk>}`. Confirm `status='processing'`. Still hidden.
12. Refresh status: `POST /api/gallery/admin/videos/<pk>/refresh-status/`. When Cloudflare is ready, `status='ready'`.
13. Confirm video NOW appears at `GET /api/public/videos/` and `GET /api/public/albums/<slug>/videos/`.
14. Confirm failed/private/unpublished content never appears on public endpoints.

---

## Remaining Risks

- **Legacy `AlbumListCreateView`** (`/api/gallery/albums/` POST) is still reachable and still creates with `is_published=False`. Frontend must be refactored to use the typed admin endpoints. Until then, any video gallery created through the old frontend flow will remain hidden.
- **Test discovery conflict** (`gallery/tests.py` vs `gallery/tests/` package) is a pre-existing issue that must be resolved separately before the test suite can be run via `manage.py test gallery`.
- **`AdminVideoItemWriteSerializer` PATCH guard** blocks setting `is_public=True` via PATCH when `status != 'ready'`. With `is_public=True` now set on create, the only path to make a failed video re-public after a Cloudflare failure is a `PATCH` once the video is `ready`. This is intentional and correct behavior.
