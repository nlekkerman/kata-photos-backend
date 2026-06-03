# Backend Full Audit — Heroku Readiness
**Date:** 2026-06-03  
**Repo:** `kata-photos-backend`  
**Source of truth:** source files, settings, models, serializers, views, services, URLs, migrations, tests

---

## 1. Executive Summary

The backend is a well-structured Django 6.0.5 / DRF 3.17.1 application with two Django apps (`gallery`, `auth_api`). All 51 tests pass. No migration drift exists. The architecture is clean relative to its scale.

**Critical blockers before Heroku deployment:**
- No `Procfile` — Heroku cannot start the application
- No `runtime.txt` — Python version is undeclared
- SQLite in use — not viable on Heroku (ephemeral filesystem, single writer)
- `gunicorn` is missing from `requirements.txt`
- `whitenoise` is missing — static file serving will fail on Heroku
- `dj-database-url` or `DATABASE_URL` handling is absent
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` are not set for production
- `SECURE_PROXY_SSL_HEADER` is not configured (required behind Heroku's TLS terminator)
- `CLOUDFLARE_STREAM_WATERMARK_UID` is absent from `.env.example`

**No dead code requiring immediate deletion.** One significant duplication risk exists: `VideoClipSyncView` and `AdminVideoRefreshStatusView` contain identical sync logic (see §5).

---

## 2. Current Backend Architecture

```
kata-photos-backend/
├── config/               — Django project settings, root URL conf, ASGI/WSGI
├── auth_api/             — Session auth: login, logout, session state, CSRF
├── gallery/              — Core app: models, serializers, views, URLs, admin
│   └── services/
│       ├── cloudflare_images.py   — Cloudflare Images upload service
│       └── cloudflare_stream.py   — Cloudflare Stream direct-upload + status sync
└── scripts/              — One-off utility scripts (not part of the app)
```

### Apps and responsibilities

| App | Responsibility |
|-----|----------------|
| `auth_api` | Login/logout/CSRF/session endpoints only |
| `gallery` | Albums, MediaItems, FieldNotes, VideoClips — all CRUD + Cloudflare integration |

### Models

| Model | Key fields | Notes |
|-------|-----------|-------|
| `Album` | `slug`, `gallery_type`, `is_published`, `display_order`, `cover_media` FK, bilingual content, SEO fields | Serves as container for both images and videos via `gallery_type` |
| `MediaItem` | `provider`, `provider_public_id`, `original_file`, `public_url`, `thumbnail_url`, bilingual content | Multi-provider: local / cloudinary / cloudflare_images / cloudflare_stream |
| `FieldNote` | `slug`, `is_published`, `published_at`, `cover_image` FK, bilingual content | Independent blog-style model |
| `VideoClip` | `cloudflare_uid`, `status`, `is_public`, `cloudflare_playback_url`, `cloudflare_thumbnail_url` | Separate from MediaItem; videos live here, not in MediaItem |

### Service layer

| Service | Location | Uses |
|---------|----------|------|
| Cloudflare Images upload | `gallery/services/cloudflare_images.py` | `urllib.request`, no third-party SDK |
| Cloudflare Stream direct upload + sync | `gallery/services/cloudflare_stream.py` | `urllib.request`, no third-party SDK |

Both services use `urllib.request` exclusively — no `requests` dependency in main app code (only in `scripts/`).

### URL structure

```
/admin/                              — Django admin
/api/auth/session/                   — GET session state
/api/auth/csrf/                      — GET CSRF cookie
/api/auth/login/                     — POST login
/api/auth/logout/                    — POST logout
/api/gallery/albums/                 — Public album list / admin create
/api/gallery/albums/<slug>/          — Public album detail / admin patch/delete
/api/gallery/albums/<slug>/cover/    — Admin: set cover image
/api/gallery/albums/<slug>/media/    — Public media list / admin image upload
/api/gallery/media/<pk>/             — Public media detail / admin patch/delete
/api/gallery/field-notes/            — Public field note list
/api/gallery/field-notes/<slug>/     — Public field note detail
/api/gallery/videos/                 — Public/admin video list
/api/gallery/videos/direct-upload/   — Admin: request Cloudflare upload URL (legacy)
/api/gallery/videos/<pk>/            — Public/admin video detail
/api/gallery/videos/<pk>/sync/       — Admin: sync video status (legacy)
/api/gallery/admin/image-galleries/  — Admin: image gallery CRUD
/api/gallery/admin/image-galleries/<pk>/
/api/gallery/admin/images/           — Admin: image item CRUD
/api/gallery/admin/images/<pk>/
/api/gallery/admin/video-galleries/  — Admin: video gallery CRUD
/api/gallery/admin/video-galleries/<pk>/
/api/gallery/admin/videos/           — Admin: video list
/api/gallery/admin/videos/direct-upload/   — Admin: request Cloudflare upload URL
/api/gallery/admin/videos/complete-upload/ — Admin: mark upload complete
/api/gallery/admin/videos/<pk>/            — Admin: video detail/patch/delete
/api/gallery/admin/videos/<pk>/refresh-status/ — Admin: sync video status
```

---

## 3. Endpoint Inventory

### Public read endpoints

| Method | Route | View | Auth | Serializer | Model |
|--------|-------|------|------|-----------|-------|
| GET | `/api/gallery/albums/` | `AlbumListCreateView` | None | `AlbumListSerializer` | Album (is_published=True) |
| GET | `/api/gallery/albums/<slug>/` | `AlbumRetrieveUpdateDestroyView` | None | `AlbumDetailSerializer` | Album (is_published=True) |
| GET | `/api/gallery/albums/<slug>/media/` | `AlbumMediaListCreateView` | None | `MediaItemPublicSerializer` | MediaItem (is_published=True, album__is_published=True) |
| GET | `/api/gallery/media/<pk>/` | `MediaItemRetrieveUpdateDestroyView` | None | `MediaItemPublicSerializer` | MediaItem (is_published=True, album__is_published=True) |
| GET | `/api/gallery/field-notes/` | `FieldNoteListView` | None | `FieldNoteListSerializer` | FieldNote (is_published=True) |
| GET | `/api/gallery/field-notes/<slug>/` | `FieldNoteDetailView` | None | `FieldNoteDetailSerializer` | FieldNote (is_published=True) |
| GET | `/api/gallery/videos/` | `VideoClipListView` | None (staff sees all) | `VideoClipSerializer` | VideoClip (is_public=True, status=ready for anon) |
| GET | `/api/gallery/videos/<pk>/` | `VideoClipDetailView` | None (staff sees all) | `VideoClipSerializer` | VideoClip |

### Auth endpoints

| Method | Route | View | Auth | Notes |
|--------|-------|------|------|-------|
| GET | `/api/auth/session/` | `SessionView` | None | Returns is_authenticated, is_staff, username |
| GET | `/api/auth/csrf/` | `CsrfView` | None | Sets CSRF cookie; `authentication_classes=[]` |
| POST | `/api/auth/login/` | `LoginView` | None | Staff only; sets session |
| POST | `/api/auth/logout/` | `LogoutView` | None | Destroys session |

### Admin write endpoints (IsAdminUser required)

| Method | Route | View | Serializer |
|--------|-------|------|-----------|
| POST | `/api/gallery/albums/` | `AlbumListCreateView` | `AlbumWriteSerializer` |
| PATCH/DELETE | `/api/gallery/albums/<slug>/` | `AlbumRetrieveUpdateDestroyView` | `AlbumWriteSerializer` |
| PATCH | `/api/gallery/albums/<slug>/cover/` | `AlbumCoverUpdateView` | `AlbumCoverWriteSerializer` |
| POST | `/api/gallery/albums/<slug>/media/` | `AlbumMediaListCreateView` | `MediaItemWriteSerializer` |
| PATCH/DELETE | `/api/gallery/media/<pk>/` | `MediaItemRetrieveUpdateDestroyView` | `MediaItemWriteSerializer` |
| POST | `/api/gallery/videos/direct-upload/` | `VideoClipDirectUploadView` | `VideoClipDirectUploadRequestSerializer` |
| POST | `/api/gallery/videos/<pk>/sync/` | `VideoClipSyncView` | — (returns `VideoClipSerializer`) |
| GET/POST | `/api/gallery/admin/image-galleries/` | `AdminImageGalleryListCreateView` | `AdminImageGallerySerializer` / `AdminImageGalleryWriteSerializer` |
| GET/PATCH/DELETE | `/api/gallery/admin/image-galleries/<pk>/` | `AdminImageGalleryRetrieveUpdateDestroyView` | — |
| GET/POST | `/api/gallery/admin/images/` | `AdminImageItemListCreateView` | `AdminImageItemSerializer` / `AdminImageItemWriteSerializer` |
| GET/PATCH/DELETE | `/api/gallery/admin/images/<pk>/` | `AdminImageItemRetrieveUpdateDestroyView` | — |
| GET/POST | `/api/gallery/admin/video-galleries/` | `AdminVideoGalleryListCreateView` | `AdminVideoGallerySerializer` / `AdminVideoGalleryWriteSerializer` |
| GET/PATCH/DELETE | `/api/gallery/admin/video-galleries/<pk>/` | `AdminVideoGalleryRetrieveUpdateDestroyView` | — |
| GET | `/api/gallery/admin/videos/` | `AdminVideoItemListView` | `AdminVideoItemSerializer` |
| POST | `/api/gallery/admin/videos/direct-upload/` | `AdminVideoDirectUploadView` | `AdminVideoDirectUploadSerializer` |
| POST | `/api/gallery/admin/videos/complete-upload/` | `AdminVideoCompleteUploadView` | `AdminVideoCompleteUploadSerializer` |
| GET/PATCH/DELETE | `/api/gallery/admin/videos/<pk>/` | `AdminVideoItemRetrieveUpdateDestroyView` | `AdminVideoItemWriteSerializer` |
| POST | `/api/gallery/admin/videos/<pk>/refresh-status/` | `AdminVideoRefreshStatusView` | — |

---

## 4. Dead Code Findings

| File | Symbol | Reason | Confidence | Recommended action |
|------|--------|--------|------------|-------------------|
| `gallery/models.py` | `MediaItem.PROVIDER_CHOICES`: `'cloudinary'` | Cloudinary provider is declared but no service code exists for it; `cloudflare_images.py` is the only image cloud service | High | Investigate — either remove choice and add migration, or document as placeholder |
| `gallery/models.py` | `MediaItem.PROVIDER_CHOICES`: `'cloudflare_stream'` | Provider exists for video URLs but `VideoClip` is the actual video model; `MediaItem` with `provider='cloudflare_stream'` is never created by any current code path | High | Investigate — consider removing to avoid confusion, or keep with documentation |
| `gallery/models.py` | `MediaItem.duration_seconds` | Duration field exists on `MediaItem` but no code path sets it for MediaItem (only `VideoClip` has duration logic) | Medium | Keep (could be used for video-in-MediaItem future), but document clearly |
| `gallery/views.py` | `VideoClipDirectUploadView` + `VideoClipSyncView` | Legacy endpoints at `/api/gallery/videos/direct-upload/` and `/api/gallery/videos/<pk>/sync/` are superseded by the admin-prefixed equivalents (`/api/gallery/admin/videos/direct-upload/` and `/api/gallery/admin/videos/<pk>/refresh-status/`). Both old and new are registered in `urls.py`. | Medium | Investigate whether frontend still uses legacy paths; if not, delete |
| `gallery/views.py` | `AdminVideoRefreshStatusView.post()` | Full copy of `VideoClipSyncView.post()` logic; both do identical Cloudflare sync. No shared helper. | High | Keep both for now, but refactor sync logic to a shared helper in Phase 3 |
| `gallery/serializers.py` | `AlbumWriteSerializer.validate()` | Duplicate slug/published validation logic appears also in `AdminImageGalleryWriteSerializer.validate()` and `AdminVideoGalleryWriteSerializer.validate()` (3 copies) | High | Refactor to a mixin or shared function in Phase 3 |
| `scripts/create_cloudflare_watermark_profile.py` | entire script | One-off script. Already run successfully (watermark profile created 2026-06-03). Uses `requests` (not in `requirements.txt`). Has no place in a Heroku slug. | High | Move to a `docs/` folder or delete after confirming UID is stored in production config |
| `gallery/models.py` | `Album.title`, `Album.description`, `Album.seo_title`, `Album.seo_description` (non-bilingual base fields) | These fields exist alongside the bilingual `_en`/`_bs` variants. Migration 0004 copied data to the `_en` fields. No serializer exposes the base fields; `__str__` references them as last fallback only. | Medium | Review whether these can be removed; requires a migration |
| `gallery/models.py` | `MediaItem.title`, `MediaItem.description`, `MediaItem.alt_text`, `MediaItem.caption` (non-bilingual base fields) | Same pattern as Album — bilingual `_en`/`_bs` variants exist; base fields are not in any serializer | Medium | Same as above |

---

## 5. Architecture Issues

### A. Duplicated sync logic (High priority)

`VideoClipSyncView.post()` and `AdminVideoRefreshStatusView.post()` contain line-for-line identical code: they both call `get_video_details`, `map_cloudflare_status`, `build_playback_url`, `build_thumbnail_url`, save the video, and return a serialized response. The only difference is that `AdminVideoRefreshStatusView` returns `AdminVideoItemSerializer` while `VideoClipSyncView` returns `VideoClipSerializer`.

**Risk:** Changes to sync logic must be made in two places. A bug fix in one will not fix the other.

**Fix:** Extract a `_sync_videoclip_from_cloudflare(video, account_id, api_token, customer_subdomain)` helper function; both views call it.

### B. Legacy vs. admin endpoint duplication

Two direct-upload endpoints exist:
- `POST /api/gallery/videos/direct-upload/` — `VideoClipDirectUploadView` — returns `VideoClipSerializer`
- `POST /api/gallery/admin/videos/direct-upload/` — `AdminVideoDirectUploadView` — returns `AdminVideoItemSerializer`

Both are active, both require `IsAdminUser`. The admin version enforces `album` must be `gallery_type=video`. The legacy version accepts any album or no album. The serializers differ (`VideoClipDirectUploadRequestSerializer` vs. `AdminVideoDirectUploadSerializer`). This creates two paths for the same operation and two partially inconsistent response shapes.

### C. `AlbumWriteSerializer` vs admin-specific serializers

`AlbumWriteSerializer`, `AdminImageGalleryWriteSerializer`, and `AdminVideoGalleryWriteSerializer` share the same `validate()` body. `AlbumWriteSerializer` is used by the legacy `AlbumListCreateView` (mixed-permission endpoint). The admin-specific write serializers are identical in validation.

### D. `gallery_type` not enforced on legacy album endpoints

`POST /api/gallery/albums/` uses `AlbumWriteSerializer` which does not set `gallery_type`. A staff user can create an album with no explicit type, defaulting to `'image'`. The admin-prefixed endpoints explicitly call `serializer.save(gallery_type=Album.GALLERY_TYPE_IMAGE)` or `GALLERY_TYPE_VIDEO`, preventing drift.

### E. Business logic partially in views

`_save_media_item_with_cloudflare()` is a module-level function in `views.py`. It contains upload orchestration logic (read bytes, extract dimensions, call service, save model) that belongs in a service layer. It is currently called by two view classes.

### F. `AdminImageItemWriteSerializer` `album` field allows re-assignment

`AdminImageItemWriteSerializer` includes `album` as a writable field, which means a PATCH could move an image from one gallery to another. This is a data-integrity concern — the album FK relationship would silently change without any validation that the target album is published or the correct type beyond the queryset filter.

---

## 6. API Contract Issues

### Inconsistent field naming: `is_public` vs. `is_published`

`VideoClip.is_public` (model field) is mapped to `is_published` in `AdminVideoItemSerializer` and `AdminVideoItemWriteSerializer`. `VideoClipSerializer` (used by public + legacy endpoints) exposes the raw `is_public` field name. This creates two different field names for the same concept depending on which endpoint is called.

| Endpoint | Field name exposed |
|----------|--------------------|
| `GET /api/gallery/videos/` | `is_public` |
| `GET /api/gallery/admin/videos/` | `is_published` |

**Risk:** Frontend must handle both names for the same boolean, or target one endpoint exclusively.

### `AlbumDetailSerializer` missing `gallery_type`

The public album detail serializer does not include `gallery_type`. A frontend consuming `GET /api/gallery/albums/<slug>/` cannot determine whether the album contains images or videos.

### `AlbumListSerializer` missing `gallery_type`

Same as above — `gallery_type` is omitted from the public list response.

### `VideoClipSerializer` exposes `album` as a raw integer FK

`VideoClipSerializer.album` is a plain integer PK. `AdminVideoItemSerializer` wraps it with `gallery_id`, `gallery_slug`, `gallery_title_bs`. The public endpoint gives less information than the admin endpoint.

### `MediaItemPublicSerializer` does not include `media_type`

Wait — checking: `media_type` is present in `MediaItemPublicSerializer.fields`. This is fine.

### FieldNote endpoints have no admin CRUD

There is no `POST /api/auth/.../field-notes/` or admin-prefixed endpoint for creating/updating FieldNotes via the API. FieldNotes must currently be managed through Django admin only. This is acceptable but should be documented.

### `VideoClipDirectUploadRequestSerializer.album` accepts any `Album` type

The legacy `VideoClipDirectUploadRequestSerializer` uses `queryset=Album.objects.all()`, allowing assignment to an image-type gallery. `AdminVideoDirectUploadSerializer` correctly restricts to `gallery_type=Album.GALLERY_TYPE_VIDEO`.

---

## 7. Image Flow Audit

### Upload path

1. `POST /api/gallery/albums/<slug>/media/` (legacy) or `POST /api/gallery/admin/images/` (admin)
2. View calls `_save_media_item_with_cloudflare(serializer, album=album)` (defined in `views.py`)
3. If `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_IMAGES_API_TOKEN` are set and `original_file` is present → calls `gallery/services/cloudflare_images.py::upload_image()`
4. If credentials are absent → saves file locally to `MEDIA_ROOT/gallery/originals/`

### Cloudflare Images credentials

- Credentials read exclusively from `settings.CLOUDFLARE_ACCOUNT_ID` and `settings.CLOUDFLARE_IMAGES_API_TOKEN`
- Never exposed in API responses
- `upload_image()` accepts `account_id`/`api_token` as parameters with fallback to settings — credentials are server-side only

### Image URL serialization

- For `provider='local'`: `_get_public_url()` resolves via `request.build_absolute_uri()`, correctly building absolute URLs
- For `provider='cloudflare_images'`: returns stored `public_url` and `thumbnail_url` directly

**Concern:** For local files, both `public_url` and `thumbnail_url` resolve to the same `original_file.url`. There is no thumbnail generation for local uploads. This means the frontend receives the full-resolution image for both `public_url` and `thumbnail_url`.

### Old Cloudflare Images logic

No remnants of deprecated Cloudflare Images code. The `cloudflare_images.py` service is clean and currently active.

### No Cloudinary integration

`PROVIDER_CHOICES` includes `'cloudinary'` but there is no Cloudinary service file, no Cloudinary credentials in settings, and no code path that saves a `MediaItem` with `provider='cloudinary'`. This is dead provider configuration.

### Media storage on Heroku

Local uploads to `MEDIA_ROOT` will be lost on Heroku dyno restart. All media must be served through Cloudflare Images in production. There is no enforcement that prevents local uploads when Cloudflare credentials are not set.

---

## 8. Video Flow Audit

### Direct upload path (admin)

1. `POST /api/gallery/admin/videos/direct-upload/` — `AdminVideoDirectUploadView`
2. Validates `AdminVideoDirectUploadSerializer` (album must be `gallery_type='video'`, `title_bs` required)
3. Reads `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_STREAM_API_TOKEN`, `CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS`, `CLOUDFLARE_STREAM_WATERMARK_UID` from `settings`
4. Calls `gallery/services/cloudflare_stream.py::create_direct_upload()` with `watermark_uid`
5. Creates `VideoClip` record with `status='uploading'`
6. Returns `{"video": AdminVideoItemSerializer(video).data, "upload_url": "..."}`

### Watermark integration

- `create_direct_upload()` conditionally includes `"watermark": {"uid": watermark_uid}` in the Cloudflare API request body only when `watermark_uid` is non-empty
- `CLOUDFLARE_STREAM_WATERMARK_UID` is read from settings in both `VideoClipDirectUploadView` (legacy) and `AdminVideoDirectUploadView`
- Watermark is burned into the video at Cloudflare's transcoding stage — no backend decoding needed

**Confirmed:** new upload requests do send:
```json
{
  "watermark": { "uid": "<CLOUDFLARE_STREAM_WATERMARK_UID>" }
}
```
when `CLOUDFLARE_STREAM_WATERMARK_UID` is set. Test `test_watermark_uid_forwarded_to_cloudflare` confirms this.

**Old videos:** Videos uploaded before the watermark profile was created will not have a watermark unless re-uploaded through the app. There is no re-watermarking API flow.

### Complete-upload path

1. `POST /api/gallery/admin/videos/complete-upload/` — `AdminVideoCompleteUploadView`
2. Accepts `video_id` or `cloudflare_uid`
3. Transitions `status: uploading → processing`
4. Does not contact Cloudflare — purely a local state transition

### Sync/refresh-status path

1. `POST /api/gallery/admin/videos/<pk>/refresh-status/` — `AdminVideoRefreshStatusView`
2. Calls `get_video_details()` from `cloudflare_stream.py`
3. Updates `status`, `duration_seconds`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`

### Playback URL format

`build_playback_url()` returns: `https://{customer_subdomain}/{uid}/iframe`  
This is the Cloudflare Stream iframe embed URL. Public frontend should embed via `<iframe>`.

### Legacy `VideoClipDirectUploadView`

At `/api/gallery/videos/direct-upload/`, this endpoint also exists. It:
- Uses `VideoClipDirectUploadRequestSerializer` (album accepts any type)
- Returns `{"video": VideoClipSerializer(video).data, "upload_url": "..."}` — different serializer than admin view
- Is registered in `urls.py` and fully functional

**Both endpoints are live and active.** This is the main conflict with the admin upload flow.

### Cloudflare Stream environment variables

All five Stream settings are read cleanly from environment:
- `CLOUDFLARE_ACCOUNT_ID` (shared with Images)
- `CLOUDFLARE_STREAM_API_TOKEN`
- `CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN`
- `CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS` (default: 3600)
- `CLOUDFLARE_STREAM_WATERMARK_UID` (default: `""`)

---

## 9. Watermark Integration Status

| Item | Status |
|------|--------|
| Watermark profile created on Cloudflare | Confirmed (script run 2026-06-03) |
| `CLOUDFLARE_STREAM_WATERMARK_UID` in settings | Present (reads from env, defaults to `""`) |
| `CLOUDFLARE_STREAM_WATERMARK_UID` in `.env.example` | **MISSING** |
| Watermark UID forwarded to Cloudflare on upload | Confirmed — `create_direct_upload()` includes `{"watermark": {"uid": uid}}` when non-empty |
| Test coverage for watermark forwarding | Present — `VideoClipDirectUploadWatermarkTests` (7 tests) |
| Admin direct-upload also sends watermark | Confirmed — `AdminVideoDirectUploadView` reads and forwards `watermark_uid` |
| Old videos re-watermarked automatically | No — watermark only on new uploads |

---

## 10. Authentication, Session, and CSRF Findings

### Endpoint behavior

| Endpoint | CSRF enforced? | Notes |
|----------|---------------|-------|
| `GET /api/auth/csrf/` | No (safe method + `authentication_classes=[]`) | Correct — used to seed CSRF token |
| `POST /api/auth/login/` | Yes (DRF enforces on session auth POST) | |
| `POST /api/auth/logout/` | Yes | |
| All write endpoints | Yes | |

### Permission model

- `LoginView` blocks non-staff users with HTTP 403 — only `is_staff=True` users can log in through the API. Correct.
- `LogoutView` has `permission_classes = [AllowAny]` — any user (including anonymous) can POST to logout. This is intentionally safe.
- `CsrfView` sets `authentication_classes = []` — prevents session lookup on a view that only needs to set a cookie. Correct.

### CORS settings

```python
CORS_ALLOWED_ORIGINS   = ["http://localhost:5173", "http://127.0.0.1:5173"]  # defaults
CORS_ALLOW_CREDENTIALS = True
```

- Production values must be set via `CORS_ALLOWED_ORIGINS` env var (e.g., `https://kata-dejanovic.netlify.app`)
- No wildcard CORS (`*`) — correct

### Cookie/SSL settings — gaps for production

| Setting | Current state | Required for production |
|---------|-------------|------------------------|
| `SESSION_COOKIE_SECURE` | Not set (defaults to `False`) | Must be `True` on Heroku (HTTPS only) |
| `CSRF_COOKIE_SECURE` | Not set (defaults to `False`) | Must be `True` on Heroku |
| `SESSION_COOKIE_SAMESITE` | Not set (Django default: `'Lax'`) | `'None'` if frontend is on a different origin (Netlify); requires `SESSION_COOKIE_SECURE=True` |
| `CSRF_COOKIE_SAMESITE` | Not set (Django default: `'Lax'`) | `'None'` for cross-origin frontend + HTTPS |
| `SECURE_PROXY_SSL_HEADER` | Not set | **Must be** `('HTTP_X_FORWARDED_PROTO', 'https')` on Heroku |
| `SECURE_SSL_REDIRECT` | Not set | Consider `True` on Heroku (or handle at Heroku router level) |
| `CSRF_COOKIE_HTTPONLY` | Not set (defaults to `False`) | Keep `False` — frontend must read the CSRF cookie via JS |

### `CSRF_TRUSTED_ORIGINS`

Defaults to `http://localhost:5173,http://127.0.0.1:5173`. Must be set to the production Netlify URL in Heroku config vars. Missing from `.env.example` for the production entry.

### `ALLOWED_HOSTS`

Defaults to `127.0.0.1,localhost`. Must include the Heroku app hostname (e.g., `kata-backend.herokuapp.com`) in production.

---

## 11. Environment Variable Inventory

| Variable | Required? | Used in | Purpose | Safe default? | Needed on Heroku? |
|----------|-----------|---------|---------|---------------|-------------------|
| `SECRET_KEY` | **Yes** | `settings.py` | Django secret key | **No** — no default, raises `KeyError` if missing | **Yes** |
| `DEBUG` | No | `settings.py` | Enable debug mode | `False` (safe) | **Yes** — must be `False` |
| `ALLOWED_HOSTS` | No | `settings.py` | Django allowed hosts | `127.0.0.1,localhost` (unsafe for prod) | **Yes** — set to Heroku hostname |
| `CSRF_TRUSTED_ORIGINS` | No | `settings.py` | CSRF origin allowlist | `http://localhost:5173,...` (unsafe for prod) | **Yes** — set to `https://` Netlify URL |
| `CORS_ALLOWED_ORIGINS` | No | `settings.py` | CORS allowlist | `http://localhost:5173,...` (unsafe for prod) | **Yes** — set to `https://` Netlify URL |
| `DATABASE_URL` | **No — not handled** | Not in `settings.py` | PostgreSQL URL on Heroku | N/A — SQLite only currently | **Yes** — requires `dj-database-url` + `psycopg2` |
| `STATIC_URL` | No | `settings.py` | Static file URL prefix | `/static/` | Optional |
| `MEDIA_URL` | No | `settings.py` | Media file URL prefix | `/media/` | N/A on Heroku (ephemeral) |
| `CLOUDFLARE_ACCOUNT_ID` | No (soft) | `settings.py`, both services | Cloudflare account ID (shared) | `""` — images/video upload silently disabled | **Yes** |
| `CLOUDFLARE_IMAGES_API_TOKEN` | No (soft) | `settings.py`, `cloudflare_images.py` | API token for image uploads | `""` — falls back to local storage | **Yes** |
| `CLOUDFLARE_STREAM_API_TOKEN` | No (soft) | `settings.py`, `cloudflare_stream.py` | API token for video uploads/sync | `""` — raises 500 if video upload attempted | **Yes** |
| `CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN` | No (soft) | `settings.py`, `VideoClipSyncView`, `AdminVideoRefreshStatusView` | Playback/thumbnail URL generation | `""` — playback URLs not built if missing | **Yes** |
| `CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS` | No | `settings.py` | Upload URL TTL | `3600` (safe) | No |
| `CLOUDFLARE_STREAM_WATERMARK_UID` | No (soft) | `settings.py` | Watermark profile UID | `""` — uploads without watermark | **Yes** — set to the created watermark UID |

**Flagged issues:**
- `CLOUDFLARE_STREAM_WATERMARK_UID` is absent from `.env.example` — must be added
- `DATABASE_URL` is referenced in Heroku's `DATABASES` implicitly but not handled in settings at all
- No `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER` env-var-driven production controls exist

---

## 12. Heroku Deployment Readiness Checklist

| Item | Status | Notes |
|------|--------|-------|
| `Procfile` | **MISSING** | Must create: `web: gunicorn config.wsgi:application` |
| `runtime.txt` | **MISSING** | Should declare e.g. `python-3.12.x` |
| `gunicorn` in `requirements.txt` | **MISSING** | Required WSGI server for Heroku |
| `whitenoise` in `requirements.txt` | **MISSING** | Required for serving static files without a CDN |
| `dj-database-url` in `requirements.txt` | **MISSING** | Required to parse `DATABASE_URL` |
| `psycopg2-binary` in `requirements.txt` | **MISSING** | Required PostgreSQL adapter |
| SQLite → PostgreSQL | **NOT DONE** | `settings.py` hardcodes SQLite; `DATABASE_URL` not handled |
| `SECRET_KEY` from env | Present | Already required from env |
| `DEBUG=False` in production | Controllable via env | Must set `DEBUG=False` on Heroku |
| `ALLOWED_HOSTS` includes Heroku hostname | Controllable via env | Must add Heroku hostname |
| `SECURE_PROXY_SSL_HEADER` | **MISSING** | Required for HTTPS detection behind Heroku router |
| `SESSION_COOKIE_SECURE` | **MISSING** | Must be `True` in production |
| `CSRF_COOKIE_SECURE` | **MISSING** | Must be `True` in production |
| `SESSION_COOKIE_SAMESITE = 'None'` | **MISSING** | Required for cross-origin session with Netlify frontend |
| `CSRF_COOKIE_SAMESITE = 'None'` | **MISSING** | Required for cross-origin CSRF with Netlify frontend |
| `CSRF_TRUSTED_ORIGINS` includes Netlify URL | Controllable via env | Must set in Heroku config vars |
| `CORS_ALLOWED_ORIGINS` includes Netlify URL | Controllable via env | Must set in Heroku config vars |
| `STATIC_ROOT` configured | Present (`staticfiles/`) | Correct |
| `collectstatic` works | Likely yes | Not verified on Heroku without whitenoise |
| `DISABLE_COLLECTSTATIC` | Not needed | Do not set; let collectstatic run |
| Logging to stdout | Partial | Django `DEBUG=False` default logging goes to console; no explicit `LOGGING` dict configured — acceptable |
| `media/` files on ephemeral filesystem | **Risk** | Local image uploads will be lost on dyno restart; acceptable only if Cloudflare Images is always used in prod |
| Migrations on release | Not automated | Should add a `release` phase in Procfile: `release: python manage.py migrate` |
| Admin user creation | Manual | Run `createsuperuser` via `heroku run` after first deploy |
| Cloudflare credentials in config vars | Not yet | Must add all 5 Cloudflare env vars |

### Required Heroku config vars

| Heroku Config Var | Required | Example / Notes |
|-------------------|----------|----------------|
| `SECRET_KEY` | **Yes** | 50+ character random string |
| `DEBUG` | **Yes** | `False` |
| `ALLOWED_HOSTS` | **Yes** | `your-app.herokuapp.com` |
| `CSRF_TRUSTED_ORIGINS` | **Yes** | `https://your-site.netlify.app` |
| `CORS_ALLOWED_ORIGINS` | **Yes** | `https://your-site.netlify.app` |
| `DATABASE_URL` | **Yes** | Auto-set by Heroku Postgres add-on |
| `CLOUDFLARE_ACCOUNT_ID` | **Yes** | Your CF account ID |
| `CLOUDFLARE_IMAGES_API_TOKEN` | **Yes** | CF Images write token |
| `CLOUDFLARE_STREAM_API_TOKEN` | **Yes** | CF Stream write token |
| `CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN` | **Yes** | e.g. `customer-abc123.cloudflarestream.com` |
| `CLOUDFLARE_STREAM_WATERMARK_UID` | **Yes** | UID from watermark profile created 2026-06-03 |
| `CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS` | No | Default `3600` is acceptable |

---

## 13. Security Risks

| Risk | Severity | Location | Notes |
|------|----------|----------|-------|
| Missing `SESSION_COOKIE_SECURE` | **High** | `settings.py` | Session cookies transmitted over HTTP on Heroku without this |
| Missing `CSRF_COOKIE_SECURE` | **High** | `settings.py` | CSRF cookies insecure over HTTP |
| Missing `SECURE_PROXY_SSL_HEADER` | **High** | `settings.py` | Django won't detect HTTPS behind Heroku's TLS terminator; `request.is_secure()` returns False |
| Missing `SESSION_COOKIE_SAMESITE='None'` | **Medium** | `settings.py` | Cross-origin session with Netlify will not work without this (combined with `Secure`) |
| No `DATABASE_URL` handling | **High** | `settings.py` | SQLite on Heroku = data loss on every dyno restart |
| `CLOUDFLARE_STREAM_WATERMARK_UID` absent from `.env.example` | Medium | `.env.example` | New developers or staging deploys will silently upload watermark-free videos |
| Local media uploads on Heroku ephemeral filesystem | Medium | `settings.py`, `_save_media_item_with_cloudflare` | If CF Images creds are missing in production, files are saved locally and will be lost |
| `requests` dependency in `scripts/` but not in `requirements.txt` | Low | `scripts/create_cloudflare_watermark_profile.py` | Script will fail to import `requests` in a fresh install unless installed separately |
| Admin Django interface at `/admin/` is enabled | Low | `config/urls.py` | Not inherently a risk; ensure `ALLOWED_HOSTS` and strong admin password in production |
| Login brute-force protection | Low | `auth_api/views.py` | No rate limiting on `POST /api/auth/login/`. Django admin throttling does not apply to the custom login endpoint |

---

## 14. Test Coverage Gaps

### Current state

- **51 tests, all passing**
- Coverage areas: album CRUD, media upload permissions, media publish validation, upload safety (type/size), album cover API, auth (session/csrf/login/logout), video direct-upload (watermark forwarding, permissions, error surface)

### Gaps

| Area | Missing tests | Priority |
|------|--------------|---------|
| Admin image gallery endpoints (`/api/gallery/admin/image-galleries/`) | No tests for list, create, update, delete, `image_count` annotation | High |
| Admin image item endpoints (`/api/gallery/admin/images/`) | No tests | High |
| Admin video gallery endpoints (`/api/gallery/admin/video-galleries/`) | No tests | High |
| Admin video item PATCH/DELETE | No tests for `AdminVideoItemRetrieveUpdateDestroyView` | High |
| `AdminVideoCompleteUploadView` | No tests for `complete-upload` state transition | High |
| `AdminVideoRefreshStatusView` | No tests | High |
| `VideoClipSyncView` (legacy) | No tests | Medium |
| `VideoClipListView` / `VideoClipDetailView` | No tests for public filtering (`is_public`, `status=ready`), `?album=` filter | Medium |
| FieldNote list/detail endpoints | No tests | Medium |
| Album detail with `?lang=bs` | No language-aware tests | Medium |
| `AlbumRetrieveUpdateDestroyView` (PATCH/DELETE) | No tests | Medium |
| `MediaItemRetrieveUpdateDestroyView` (public GET) | No tests for public single-item retrieval with unpublished album guard | Medium |
| Cloudflare Images upload path (with mocked service) | No tests — currently only local path exercised | Medium |
| Cloudflare Images service error → 502 response | No tests | Medium |
| `VideoClipDirectUploadView` (legacy) | No tests for legacy vs. admin endpoint divergence | Low |
| `AlbumCoverWriteSerializer` — non-image media as cover | Tested. Covered. | — |
| Migration 0004 (data migration) | Not tested at test level — safe since it's already applied | Low |

---

## 15. Recommended Phased Cleanup Plan

---

### Phase 1 — Must fix before deployment

These block Heroku deployment or present critical security risks.

| # | Recommendation | Affected files | Reason | Risk | Prompt title | Diff size |
|---|---------------|---------------|--------|------|-------------|-----------|
| 1.1 | Add `Procfile` with `web:` and `release:` commands | `Procfile` (new) | Heroku cannot start without it; `migrate` on release prevents schema drift | Low | `Add Procfile for Heroku deployment` | Small |
| 1.2 | Add `runtime.txt` | `runtime.txt` (new) | Pin Python version for reproducible builds | Low | `Add runtime.txt` | Small |
| 1.3 | Add `gunicorn`, `whitenoise`, `dj-database-url`, `psycopg2-binary` to `requirements.txt` | `requirements.txt` | Required dependencies for Heroku | Low | `Add Heroku production dependencies` | Small |
| 1.4 | Add `DATABASE_URL` parsing to `settings.py` | `config/settings.py` | SQLite will lose all data on dyno restart | Medium | `Add PostgreSQL DATABASE_URL support` | Small |
| 1.5 | Add production security settings to `settings.py` | `config/settings.py` | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SAMESITE='None'`, `CSRF_COOKIE_SAMESITE='None'` — all env-driven | Medium | `Add production cookie and proxy security settings` | Small |
| 1.6 | Add `whitenoise` middleware and `STATICFILES_STORAGE` | `config/settings.py`, `requirements.txt` | Static files not served correctly without it on Heroku | Low | `Configure WhiteNoise for static file serving` | Small |
| 1.7 | Add `CLOUDFLARE_STREAM_WATERMARK_UID` to `.env.example` | `.env.example` | Prevents silent watermark-free uploads in new environments | Low | `Document CLOUDFLARE_STREAM_WATERMARK_UID in .env.example` | Small |

---

### Phase 2 — Should fix soon

Important for correctness and frontend contract consistency.

| # | Recommendation | Affected files | Reason | Risk | Prompt title | Diff size |
|---|---------------|---------------|--------|------|-------------|-----------|
| 2.1 | Add `gallery_type` to `AlbumListSerializer` and `AlbumDetailSerializer` | `gallery/serializers.py` | Frontend cannot distinguish image vs. video galleries from public API | Low | `Expose gallery_type in public album serializers` | Small |
| 2.2 | Deprecate/remove legacy video endpoints (`/api/gallery/videos/direct-upload/`, `/api/gallery/videos/<pk>/sync/`) after confirming frontend uses admin paths | `gallery/urls.py`, `gallery/views.py` | Duplicate endpoints with slightly different behavior and response shapes | Medium | `Remove legacy video upload and sync endpoints` | Medium |
| 2.3 | Fix `is_public` vs. `is_published` naming inconsistency | `gallery/serializers.py` (VideoClipSerializer) | Two field names for the same boolean across two endpoints | Low | `Normalize VideoClip is_public/is_published field naming` | Small |
| 2.4 | Add rate limiting or login throttle to `LoginView` | `auth_api/views.py` | No brute-force protection on admin login | Medium | `Add DRF throttle to login endpoint` | Small |
| 2.5 | Remove `'cloudinary'` from `MediaItem.PROVIDER_CHOICES` or add a migration note | `gallery/models.py` | Dead provider choice creates confusion; no service code exists | Low | `Remove unused Cloudinary provider choice from MediaItem` | Small |
| 2.6 | Prevent local media uploads in production | `gallery/views.py` `_save_media_item_with_cloudflare` | Files saved locally on Heroku's ephemeral FS will be lost | Medium | `Enforce Cloudflare Images in production, block local fallback` | Small |

---

### Phase 3 — Cleanup and refactor

Dead code, architecture polish, test improvements.

| # | Recommendation | Affected files | Reason | Risk | Prompt title | Diff size |
|---|---------------|---------------|--------|------|-------------|-----------|
| 3.1 | Extract shared sync logic from `VideoClipSyncView` and `AdminVideoRefreshStatusView` into a shared helper | `gallery/views.py` | Two copies of identical sync code | Low | `Deduplicate VideoClip sync logic into shared helper` | Medium |
| 3.2 | Move `_save_media_item_with_cloudflare()` from `views.py` to a service layer | `gallery/views.py`, `gallery/services/` | Business logic in views file | Low | `Move image upload orchestration to service layer` | Medium |
| 3.3 | Consolidate `AlbumWriteSerializer`, `AdminImageGalleryWriteSerializer`, `AdminVideoGalleryWriteSerializer` validation into a shared mixin | `gallery/serializers.py` | Three copies of identical `validate()` method | Low | `Deduplicate album write serializer validation` | Small |
| 3.4 | Evaluate and remove non-bilingual base fields on `Album` and `MediaItem` (`title`, `description`, `alt_text`, `caption`, `seo_title`, `seo_description`) | `gallery/models.py`, migration | Legacy fields; migration 0004 already moved content to `_en` fields; no serializer exposes them | Medium | `Remove legacy non-bilingual base fields from Album and MediaItem` | Large |
| 3.5 | Move `scripts/` one-off scripts to documentation or delete | `scripts/create_cloudflare_watermark_profile.py` | Already executed; `requests` dependency not in `requirements.txt`; not part of app | Low | `Archive or delete completed one-off scripts` | Small |
| 3.6 | Add tests for admin gallery/image/video endpoints | `gallery/tests.py` | Major endpoints have zero test coverage | Low | `Add admin gallery API test suite` | Large |
| 3.7 | Add tests for `VideoClipListView`, `VideoClipDetailView`, `FieldNoteListView`, `FieldNoteDetailView` | `gallery/tests.py` | Public read endpoints untested | Low | `Add public read endpoint tests` | Medium |
| 3.8 | Add tests for Cloudflare Images upload path (mocked) | `gallery/tests.py` | Upload-to-cloudflare code path has no test coverage | Low | `Add mocked Cloudflare Images upload tests` | Medium |

---

## Validation Commands Run

| Command | Result |
|---------|--------|
| `python manage.py check` | 0 issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test --verbosity=2` | 51 tests, 0 failures, 0 errors |

All validation commands ran successfully in the local dev environment.
