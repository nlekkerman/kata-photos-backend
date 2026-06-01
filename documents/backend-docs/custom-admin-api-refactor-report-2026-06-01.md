# Custom Admin Interface API Refactor Report
**Date:** 2026-06-01  
**Repository:** `kata-photos-backend`  
**Phase coverage:** Phase 1 (Audit), Phase 2 (Admin API endpoints), Phase 3 (Video upload flow), Phase 4 (Image upload flow cleanup), Phase 5 (Django admin improvements)

---

## Summary

Refactored the backend API to support a custom frontend admin dashboard with fully separated image gallery and video gallery management workflows. No model data was lost. No frontend files were changed. No fake or mock data was introduced.

Key changes:
- Added `gallery_type` field to `Album` (non-breaking migration, default `'image'`).
- Created 9 new admin-only API serializers.
- Created 11 new admin-only API views.
- Added 11 new URL routes under `/api/gallery/admin/`.
- Extracted the Cloudflare Images upload logic into a shared module-level helper.
- Improved Django admin registration for `Album` to show `gallery_type`.
- All 44 existing tests continue to pass.

---

## Current Architecture Discovered from Code

### 1. Gallery / Album Models

**`Album`** (`gallery/models.py`)
- Shared gallery model used for both image and video content.
- Fields: `title`, `slug`, `description`, `is_published`, `display_order`, `cover_media (FK→MediaItem)`, `seo_title/description`, `title_en/bs`, `description_en/bs`, `seo_title_en/bs`, `seo_description_en/bs`, `created_at`, `updated_at`.
- Did **not** previously distinguish image galleries from video galleries.

### 2. Image / Media Models

**`MediaItem`** (`gallery/models.py`)
- Image-centric model. `media_type` field (`'image'` | `'video'`) exists but in practice only `'image'` is used; video content uses `VideoClip`.
- Fields: `album (FK)`, `media_type`, `title/description/alt_text/caption` (en/bs), `tags`, `is_published`, `display_order`, `provider` (`local` | `cloudinary` | `cloudflare_images` | `cloudflare_stream`), `provider_public_id`, `original_file`, `public_url`, `thumbnail_url`, `width`, `height`, `duration_seconds`, `file_size`, `created_at`, `updated_at`.
- On save, local uploads auto-populate `width`, `height`, `file_size`.

### 3. Video Models

**`VideoClip`** (`gallery/models.py`)
- Separate model for Cloudflare Stream videos.
- Fields: `album (FK→Album, nullable)`, `title_bs`, `title_en`, `description_bs`, `description_en`, `cloudflare_uid (unique)`, `cloudflare_thumbnail_url`, `cloudflare_playback_url`, `duration_seconds`, `status` (`uploading` | `processing` | `ready` | `failed`), **`is_public`** (bool, default False), `created_at`, `updated_at`.
- Note: field is named `is_public` (not `is_published`). Admin serializers expose it as `is_published` via `source='is_public'`.

### 4. Cloudinary Integration

**Not active.** The `provider` choice `'cloudinary'` exists on `MediaItem` but there is no Cloudinary service file. The active image provider is **Cloudflare Images** (`gallery/services/cloudflare_images.py`).

### 5. Cloudflare Stream Integration

`gallery/services/cloudflare_stream.py` provides:
- `create_direct_upload()` — creates a Cloudflare Stream direct-upload URL.
- `get_video_details()` — fetches live video details from Cloudflare.
- `map_cloudflare_status()` — maps Cloudflare `status.state` to local status strings.
- `build_playback_url()`, `build_thumbnail_url()` — construct CDN URLs from `customer_subdomain` + `uid`.

### 6. Direct Upload Endpoints (pre-refactor)

- `POST /api/gallery/videos/direct-upload/` — `VideoClipDirectUploadView`. Staff only. Creates `VideoClip` with `status='uploading'`, returns `{ video, upload_url }`.
- No complete-upload endpoint existed before this refactor.

### 7. Save / Finalize Flow (pre-refactor)

After frontend uploads to Cloudflare, status update required a separate call to:
- `POST /api/gallery/videos/<pk>/sync/` — `VideoClipSyncView`. Staff only. Calls Cloudflare API for live status/URL update.

There was no lightweight "I'm done uploading" signal endpoint — that is introduced in this refactor as `/admin/videos/complete-upload/`.

### 8. Serializers (pre-refactor)

| Serializer | Purpose |
|---|---|
| `AlbumWriteSerializer` | Create/update Album |
| `AlbumListSerializer` | Public album list (translated) |
| `AlbumDetailSerializer` | Public album detail (translated) |
| `AlbumCoverWriteSerializer` | Set album cover media |
| `MediaCoverSerializer` | Thumbnail + alt for cover |
| `MediaItemWriteSerializer` | Create/update MediaItem |
| `MediaItemPublicSerializer` | Public media response (translated) |
| `FieldNoteListSerializer` | Public field note list |
| `FieldNoteDetailSerializer` | Public field note detail |
| `VideoClipSerializer` | Video read/write (legacy public+admin mixed) |
| `VideoClipDirectUploadRequestSerializer` | Body for legacy direct-upload |

### 9. API Views / Viewsets (pre-refactor)

All were class-based views inheriting from `generics.*`. No ViewSets.

| View | Method | Permission |
|---|---|---|
| `AlbumListCreateView` | GET/POST | GET: AllowAny, POST: IsAdminUser |
| `AlbumRetrieveUpdateDestroyView` | GET/PATCH/DELETE | GET: AllowAny, PATCH/DELETE: IsAdminUser |
| `AlbumCoverUpdateView` | PATCH | IsAdminUser |
| `AlbumMediaListCreateView` | GET/POST | GET: AllowAny, POST: IsAdminUser |
| `MediaItemRetrieveUpdateDestroyView` | GET/PATCH/DELETE | GET: AllowAny, PATCH/DELETE: IsAdminUser |
| `FieldNoteListView` | GET | AllowAny |
| `FieldNoteDetailView` | GET | AllowAny |
| `VideoClipListView` | GET | AllowAny (filters for non-staff) |
| `VideoClipDirectUploadView` | POST | IsAdminUser |
| `VideoClipDetailView` | GET | AllowAny (filters for non-staff) |
| `VideoClipSyncView` | POST | IsAdminUser |

### 10. URL Routes (pre-refactor)

All under `/api/gallery/`:
```
albums/
albums/<slug>/
albums/<slug>/cover/
albums/<slug>/media/
media/<pk>/
field-notes/
field-notes/<slug>/
videos/
videos/direct-upload/
videos/<pk>/
videos/<pk>/sync/
```

### 11. Permissions / Authentication

- Session-based auth (Django sessions + CSRF).
- `IsAdminUser` = authenticated + `is_staff=True`.
- CORS configured via `CORS_ALLOWED_ORIGINS` env var.
- `CORS_ALLOW_CREDENTIALS = True` (required for session cookies cross-origin).
- Login restricted to staff-only (`auth_api/views.py` `LoginView`).

### 12. Status Handling for Videos

Four statuses on `VideoClip.status`:
- `uploading` — set at `VideoClip` creation.
- `processing` — set by `complete-upload` (new) or `sync` endpoints.
- `ready` — set by sync when Cloudflare `status.state == 'ready'` or `readyToStream == True`.
- `failed` — set by sync when Cloudflare `status.state == 'error'`.

### 13. Published / Draft Visibility

| Endpoint type | Returns |
|---|---|
| Public album list | `is_published=True` only |
| Public album detail | `is_published=True` only |
| Public media list (nested) | `is_published=True, album.is_published=True` |
| Public media detail | `is_published=True, album.is_published=True` |
| Public video list/detail | `is_public=True, status='ready'` |
| Admin endpoints (new) | **All records** regardless of published/status |

### 14. Django Admin Registrations (pre-refactor)

- `AlbumAdmin` — list by `title_bs`, `slug`, `is_published`, `display_order`.
- `MediaItemAdmin` — list by `id`, `title_en`, `album`, `media_type`, `provider`, `is_published`.
- `FieldNoteAdmin` — list by `title_en`, `slug`, `is_published`, `published_at`.
- `VideoClipAdmin` — list by `title_bs`, `album`, `cloudflare_uid`, `status`, `is_public`.

---

## Architecture Decision

### Option Chosen: Option A with `gallery_type` extension

**Rationale:**
- Existing `Album` model already serves as the gallery concept for both images and videos. `VideoClip` and `MediaItem` both FK to `Album`.
- Adding a single `gallery_type` field (`'image'` | `'video'`, default `'image'`) to `Album` is the minimal safe change: one non-breaking migration, no data loss, existing records default to `'image'`.
- Admin endpoints filter by `gallery_type` to present clean separated workflows.
- Public endpoints are unchanged — they continue to work as before.
- The frontend admin UX sees completely separate image and video gallery namespaces even though backend storage remains unified.
- Options B and C would require new models, data migrations, and potential breakage of existing Album FK references.

### Why not Option B (shared Gallery + separate ImageItem/VideoItem)?
- Would require renaming `Album` or creating a parallel `Gallery` model.
- `MediaItem` and `VideoClip` are already well-separated; no benefit in this scope.

### Why not Option C (separate ImageGallery, VideoGallery, ImageItem, VideoItem)?
- Highest migration risk.
- All existing FK references, tests, and URLs would need updating.
- No clear benefit given the existing model structure is already de facto separated.

---

## Files Changed

| File | Change type |
|---|---|
| `gallery/models.py` | Added `gallery_type` field + constants to `Album` |
| `gallery/migrations/0009_album_gallery_type.py` | New migration (AddField) |
| `gallery/serializers.py` | Added 9 admin serializers |
| `gallery/views.py` | Refactored Cloudflare upload to shared helper; added 11 admin views |
| `gallery/urls.py` | Added 11 admin URL patterns; updated imports |
| `gallery/admin.py` | Updated `AlbumAdmin` to show `gallery_type` in list/filters/fieldsets |

No frontend files were modified.

---

## Migrations Created

| Migration | Operation |
|---|---|
| `gallery/0009_album_gallery_type.py` | `AddField(Album, 'gallery_type', CharField(max_length=10, default='image'))` |

- Non-breaking: existing albums default to `'image'`.
- Applied successfully: `Applying gallery.0009_album_gallery_type... OK`.

---

## API Endpoints Added / Changed

### New admin endpoints (all require `IsAdminUser`)

#### Image Galleries
| Method | URL | Description |
|---|---|---|
| GET | `/api/gallery/admin/image-galleries/` | List all image galleries (all published states) |
| POST | `/api/gallery/admin/image-galleries/` | Create image gallery |
| GET | `/api/gallery/admin/image-galleries/<id>/` | Retrieve image gallery |
| PATCH | `/api/gallery/admin/image-galleries/<id>/` | Update image gallery |
| DELETE | `/api/gallery/admin/image-galleries/<id>/` | Delete image gallery |

#### Image Items
| Method | URL | Description |
|---|---|---|
| GET | `/api/gallery/admin/images/?gallery=<id>` | List images (filtered by gallery if provided) |
| POST | `/api/gallery/admin/images/` | Upload image to a gallery |
| GET | `/api/gallery/admin/images/<pk>/` | Retrieve image item |
| PATCH | `/api/gallery/admin/images/<pk>/` | Update image metadata |
| DELETE | `/api/gallery/admin/images/<pk>/` | Delete image record |

#### Video Galleries
| Method | URL | Description |
|---|---|---|
| GET | `/api/gallery/admin/video-galleries/` | List all video galleries (all published states) |
| POST | `/api/gallery/admin/video-galleries/` | Create video gallery |
| GET | `/api/gallery/admin/video-galleries/<id>/` | Retrieve video gallery |
| PATCH | `/api/gallery/admin/video-galleries/<id>/` | Update video gallery |
| DELETE | `/api/gallery/admin/video-galleries/<id>/` | Delete video gallery |

#### Video Items
| Method | URL | Description |
|---|---|---|
| GET | `/api/gallery/admin/videos/?gallery=<id>` | List videos (filtered by gallery if provided) |
| POST | `/api/gallery/admin/videos/direct-upload/` | Request Cloudflare Stream direct-upload URL |
| POST | `/api/gallery/admin/videos/complete-upload/` | Signal upload done → set status to 'processing' |
| GET | `/api/gallery/admin/videos/<pk>/` | Retrieve video item |
| PATCH | `/api/gallery/admin/videos/<pk>/` | Update video metadata |
| DELETE | `/api/gallery/admin/videos/<pk>/` | Delete video record (not Cloudflare asset) |
| POST | `/api/gallery/admin/videos/<pk>/refresh-status/` | Sync status/URLs from Cloudflare Stream |

### Existing endpoints — unchanged

All existing public and legacy admin endpoints (`/api/gallery/albums/`, `/api/gallery/videos/`, `/api/gallery/media/`, etc.) are preserved and unmodified.

---

## Serializer Fields Added / Changed

### New serializers

#### `AdminImageGallerySerializer` (read)
Fields: `id`, `slug`, `title_bs`, `title_en`, `description_bs`, `description_en`, `is_published`, `display_order`, `image_count` (annotated), `cover` (nested), `created_at`, `updated_at`

#### `AdminImageGalleryWriteSerializer` (write)
Fields: `id`, `slug`, `title_bs`, `description_bs`, `seo_title_bs`, `seo_description_bs`, `title_en`, `description_en`, `seo_title_en`, `seo_description_en`, `display_order`, `is_published`  
Required on create: `title_bs`. `slug` auto-generated from `title_bs` if omitted.

#### `AdminVideoGallerySerializer` (read)
Fields: `id`, `slug`, `title_bs`, `title_en`, `description_bs`, `description_en`, `is_published`, `display_order`, `video_count`, `ready_video_count`, `processing_video_count`, `failed_video_count` (all annotated), `cover` (nested), `created_at`, `updated_at`

#### `AdminVideoGalleryWriteSerializer` (write)
Same field set as `AdminImageGalleryWriteSerializer`.

#### `AdminImageItemSerializer` (read)
Fields: `id`, `gallery_id`, `gallery_slug`, `gallery_title_bs`, `title_bs`, `title_en`, `description_bs`, `description_en`, `provider_public_id`, `public_url`, `thumbnail_url`, `is_published`, `display_order`, `width`, `height`, `file_size`, `created_at`, `updated_at`

#### `AdminImageItemWriteSerializer` (write)
Adds `album` (PK, required on create, filtered to `gallery_type='image'`) to MediaItem write fields.  
Required on create: `album`, `original_file`.

#### `AdminVideoItemSerializer` (read)
Fields: `id`, `gallery_id`, `gallery_slug`, `gallery_title_bs`, `title_bs`, `title_en`, `description_bs`, `description_en`, `cloudflare_uid`, `cloudflare_thumbnail_url`, `cloudflare_playback_url`, `duration_seconds`, `status`, **`is_published`** (`source='is_public'`), `created_at`, `updated_at`

#### `AdminVideoItemWriteSerializer` (write)
Writable: `album`, `title_bs`, `title_en`, `description_bs`, `description_en`, **`is_published`** (`source='is_public'`).  
Read-only: `cloudflare_uid`, `cloudflare_thumbnail_url`, `cloudflare_playback_url`, `duration_seconds`, `status`.

#### `AdminVideoDirectUploadSerializer`
Same fields as legacy `VideoClipDirectUploadRequestSerializer` but `album` is filtered to `gallery_type='video'`.

#### `AdminVideoCompleteUploadSerializer`
Fields: `video_id` (int, optional) or `cloudflare_uid` (str, optional). At least one required.

### Changed: `AlbumAdmin` (Django admin)
- Added `gallery_type` to `list_display`, `list_filter`, `ordering`, and `fieldsets`.

---

## Permission Behavior

| Endpoint group | Permission class | Who can access |
|---|---|---|
| All `/api/gallery/admin/*` | `IsAdminUser` | Authenticated staff only |
| `GET /api/gallery/albums/` | `AllowAny` | Public |
| `POST /api/gallery/albums/` | `IsAdminUser` | Staff only |
| `GET /api/gallery/videos/` | `AllowAny` | Public (filtered to ready+public) |
| `POST /api/gallery/videos/direct-upload/` | `IsAdminUser` | Staff only |
| All other existing endpoints | unchanged | unchanged |

- CSRF enforcement is preserved (no `csrf_exempt` added).
- Session cookie auth is compatible with the existing frontend `APIClient`.
- No security weakening.

---

## Upload Flow Details — Images

### New admin flow (`POST /api/gallery/admin/images/`)

1. Frontend sends `multipart/form-data` with `album` (image gallery PK), `original_file`, and optional metadata (`title_bs`, `alt_text_bs`, etc.).
2. `AdminImageItemListCreateView.perform_create()` calls `_save_media_item_with_cloudflare(serializer, album=album)`.
3. **If Cloudflare Images is configured** (`CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_IMAGES_API_TOKEN` are set):
   - Reads file bytes, extracts `width`/`height` via Pillow.
   - Calls `gallery.services.cloudflare_images.upload_image()`.
   - Saves `MediaItem` with `provider='cloudflare_images'`, `provider_public_id`, `public_url`, `thumbnail_url`, `original_file=None`.
4. **If Cloudflare Images is not configured:**
   - Saves `MediaItem` with `provider='local'`, file stored at `MEDIA_ROOT/gallery/originals/`.
5. `media_type='image'` is set automatically — frontend does not need to send it.
6. Returns `AdminImageItemSerializer` response (201).

### Django fields stored
`album`, `media_type='image'`, `title_bs`, `title_en`, `description_bs`, `description_en`, `alt_text_bs`, `caption_bs`, `provider`, `provider_public_id`, `public_url`, `thumbnail_url`, `display_order`, `is_published`, `width`, `height`, `file_size`

---

## Upload Flow Details — Videos

### Admin direct-upload flow

**Step 1 — Request upload URL**  
`POST /api/gallery/admin/videos/direct-upload/`

Request body:
```json
{
  "album": 5,
  "title_bs": "Naslov videa",
  "title_en": "Video title",
  "description_bs": "Opis...",
  "description_en": "Description...",
  "max_duration_seconds": 300
}
```

Response (201):
```json
{
  "video": { "id": 12, "cloudflare_uid": "abc123...", "status": "uploading", ... },
  "upload_url": "https://upload.videodelivery.net/..."
}
```

Django creates `VideoClip` with `status='uploading'`, stores `cloudflare_uid`.

**Step 2 — Frontend uploads directly to Cloudflare**  
Frontend performs a `PUT` or `POST` (per tus protocol) to `upload_url` with the raw video file. Django is not involved.

**Step 3 — Signal completion**  
`POST /api/gallery/admin/videos/complete-upload/`

Request body (use either field):
```json
{ "video_id": 12 }
```
or:
```json
{ "cloudflare_uid": "abc123..." }
```

Django updates `status` from `'uploading'` to `'processing'` and returns updated `AdminVideoItemSerializer`. Cloudflare starts processing asynchronously.

**Step 4 — Poll / refresh status**  
`POST /api/gallery/admin/videos/<pk>/refresh-status/`

Calls Cloudflare API, updates `status`, `duration_seconds`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`. Returns updated `AdminVideoItemSerializer`.

### Django fields stored
`album`, `title_bs`, `title_en`, `description_bs`, `description_en`, `cloudflare_uid`, `cloudflare_thumbnail_url`, `cloudflare_playback_url`, `duration_seconds`, `status`, `is_public`

---

## Commands Run

```
python manage.py check
→ System check identified no issues (0 silenced). EXIT:0

python manage.py makemigrations --check
→ No changes detected. EXIT:0

python manage.py migrate
→ Applying gallery.0009_album_gallery_type... OK. EXIT:0

python manage.py test --verbosity=2
→ Ran 44 tests in 40.515s — OK. EXIT:0
```

---

## Validation Results

| Check | Result |
|---|---|
| `manage.py check` | No issues |
| `manage.py makemigrations --check` | No unapplied changes |
| `manage.py migrate` | Migration 0009 applied successfully |
| Test suite (44 tests) | All pass — no regressions |
| No frontend files changed | Confirmed |
| No mock/fake data added | Confirmed |

---

## Edge Cases Handled

1. **URL routing order** — Fixed-path segments `direct-upload` and `complete-upload` are registered before `<int:pk>` in `urls.py` to prevent routing ambiguity. Django's `int` path converter would not match strings anyway, but explicit ordering is safer.

2. **`gallery_type` enforcement on `AdminImageItemWriteSerializer.album`** — The `album` PrimaryKeyRelatedField queryset is `Album.objects.filter(gallery_type='image')`. A frontend submitting an image to a video gallery will receive a 400 validation error.

3. **`media_type='image'` auto-set** — The `_save_media_item_with_cloudflare` helper always sets `media_type='image'`. The frontend admin endpoint does not expose `media_type` as a writable field.

4. **`is_public` → `is_published` mapping** — `AdminVideoItemSerializer` maps `VideoClip.is_public` to `is_published` on read. `AdminVideoItemWriteSerializer` maps incoming `is_published` back to `is_public` via `source='is_public'`.

5. **`complete-upload` idempotency** — If a video is already past `uploading` status, the endpoint returns the current record without resetting status.

6. **Annotated querysets for gallery counts** — `image_count`, `video_count`, and per-status video counts are Django ORM annotations using `Count` + `Q` filters. They hit the DB in a single query per list page.

7. **`_save_media_item_with_cloudflare` refactor** — The Cloudflare Images upload logic was extracted from the method-level `_perform_create_cloudflare` into a module-level function `_save_media_item_with_cloudflare`. The legacy `AlbumMediaListCreateView.perform_create` now delegates to this shared function. Behavior is identical.

---

## Known Limitations

1. **No `gallery_type` backfill for existing albums.** Existing albums in the database default to `gallery_type='image'`. If any existing albums were used as video-only galleries, they will not appear in the admin video-gallery endpoints until manually updated via Django admin or a data migration. This is intentional — a manual decision to reclassify is safer than an automated guess.

2. **`VideoClip` DELETE does not remove Cloudflare asset.** Deleting a `VideoClip` via `DELETE /api/gallery/admin/videos/<pk>/` removes the Django record only. The Cloudflare Stream asset must be deleted separately via the Cloudflare dashboard or API. This is documented in the view docstring.

3. **Image item PATCH with new `original_file` leaves old file on disk.** This limitation pre-existed in `MediaItemWriteSerializer` and is preserved. Orphaned file cleanup remains out of scope for this phase.

4. **No `gallery_type` field on the legacy `/api/gallery/albums/` endpoints.** Public album endpoints do not expose or filter by `gallery_type`. This is intentional — the legacy endpoints are unchanged. The admin endpoints handle type-aware access.

5. **`album` field on `AdminVideoDirectUploadSerializer` requires a `gallery_type='video'` album.** If a video gallery does not yet exist when the first video is uploaded, the frontend must create it first.

---

## Next Frontend Contract Notes

### Authentication
All admin endpoints require a valid Django session (cookie-based). Frontend must:
1. Call `GET /api/auth/csrf/` to set the CSRF cookie.
2. Call `POST /api/auth/login/` with `{ username, password }`.
3. Include `X-CSRFToken` header on all mutating requests.

### Image gallery IDs vs slugs
Admin image gallery endpoints use integer PK (`/admin/image-galleries/<id>/`). The frontend should store and use the `id` field for admin navigation, and `slug` for public URL generation.

### Video status polling
After `complete-upload`, Cloudflare processes the video asynchronously. The frontend should poll `GET /api/gallery/admin/videos/<pk>/` and check `status`, or call `POST /api/gallery/admin/videos/<pk>/refresh-status/` to trigger a live sync.

### `is_published` field (videos)
- Admin read: `is_published` (mapped from `VideoClip.is_public`).
- Admin write (PATCH body): `is_published` (mapped back to `is_public` by serializer).
- Legacy public video endpoint (`/api/gallery/videos/`): uses `is_public` field name in `VideoClipSerializer`.

### Bosnian-first field order in forms
Admin write serializers expose Bosnian fields first: `title_bs`, `description_bs`, then `title_en`, `description_en`. This matches the agreed Bosnian-first product direction.

---

## Confirmation

- **No frontend files were edited.** ✅
- **No mock or fake data was added.** ✅
- **No mock upload flow exists.** ✅
- **No fallback logic that pretends uploads succeeded.** ✅
- All API behaviour is derived from real models and real service integrations.

---

## Approximate Changed-Line Count

| File | Approx. lines changed/added |
|---|---|
| `gallery/models.py` | +12 |
| `gallery/migrations/0009_album_gallery_type.py` | +20 (new file) |
| `gallery/serializers.py` | +290 (new admin serializers) |
| `gallery/views.py` | +340 (shared helper + 11 admin views, refactor of `AlbumMediaListCreateView`) |
| `gallery/urls.py` | +30 (11 new URL patterns + imports) |
| `gallery/admin.py` | +5 (gallery_type in AlbumAdmin) |
| **Total** | **~700 lines** |
