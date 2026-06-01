# Cloudflare Images Upload Foundation — Phase 8 Implementation Report

**Date:** 2026-06-01
**Repository:** `kata-photos-backend`
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)
**Prerequisite:** Phase 7 — `documents/backend-docs/frontend-session-auth-readiness-phase-7-report-2026-06-01.md`

---

## Summary

Phase 8 adds a minimal, clean Cloudflare Images upload foundation to the gallery API. When `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_IMAGES_API_TOKEN` are set in `.env`, image uploads via `POST /api/gallery/albums/<slug>/media/` are routed to Cloudflare Images instead of local disk. When those env vars are absent, the existing local upload behavior is preserved unchanged.

No new pip dependencies were added. No frontend files were touched. No video upload logic was added.

---

## Files Inspected

| File | Reason |
|---|---|
| `gallery/models.py` | Understand existing `MediaItem` provider/URL fields |
| `gallery/serializers.py` | Understand write serializer fields and validation |
| `gallery/views.py` | Understand `perform_create` and upload flow |
| `gallery/urls.py` | Confirm upload endpoint already exists |
| `config/settings.py` | Find where to add Cloudflare env settings |
| `requirements.txt` | Confirm `requests` is NOT present (used stdlib instead) |

---

## Files Changed

| File | Change |
|---|---|
| `config/settings.py` | Added `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_IMAGES_API_TOKEN` settings |
| `gallery/models.py` | Added `'cloudflare_images'` to `PROVIDER_CHOICES` |
| `gallery/services/__init__.py` | New — empty package marker |
| `gallery/services/cloudflare_images.py` | New — `upload_image()` service and `CloudflareUploadError` |
| `gallery/views.py` | Added `CloudflareServiceError`, updated `AlbumMediaListCreateView.perform_create` |
| `gallery/serializers.py` | Added `provider`, `public_url`, `thumbnail_url`, `provider_public_id` as read-only response fields in `MediaItemWriteSerializer` |
| `gallery/migrations/0007_alter_mediaitem_provider.py` | Auto-generated — adds `cloudflare_images` to `choices` |

**Total files changed: 7** (at hard cap)
**No new pip dependency added.** Uses Python stdlib `urllib.request` for the HTTP call.

---

## Environment Variables Required

Add to `.env`:

```
CLOUDFLARE_ACCOUNT_ID=your_account_id_here
CLOUDFLARE_IMAGES_API_TOKEN=your_images_api_token_here
```

| Variable | Required | Description |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Yes (for CF uploads) | Cloudflare account ID |
| `CLOUDFLARE_IMAGES_API_TOKEN` | Yes (for CF uploads) | API token with Cloudflare Images write permission |

If either variable is empty, all uploads fall back to local disk (existing behavior). No error is raised when the variables are absent.

**Security:** The API token is read only from env at upload time inside the service. It is never serialized, logged, or included in any API response.

---

## Cloudflare Images Service

**File:** `gallery/services/cloudflare_images.py`

| Symbol | Description |
|---|---|
| `CloudflareUploadError` | Exception raised on any Cloudflare failure |
| `upload_image(file_bytes, *, filename, content_type, account_id, api_token)` | Uploads bytes to Cloudflare Images API; returns `{cf_id, public_url, thumbnail_url}` |

### Upload flow

1. Builds a multipart/form-data body using stdlib (no `requests` library)
2. POSTs to `https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1`
3. On HTTP error: raises `CloudflareUploadError` with status code (token NOT included in message)
4. On network error: raises `CloudflareUploadError`
5. On API-level error (`success: false`): raises `CloudflareUploadError` with error codes
6. On success: extracts `id` and `variants` from the Cloudflare response

### Return shape

```python
{
    "cf_id": "ZxR0pLaXRldVBmZQdtO671234",
    "public_url": "https://imagedelivery.net/{hash}/{id}/public",
    "thumbnail_url": "https://imagedelivery.net/{hash}/{id}/thumbnail",  # or same as public_url
}
```

`thumbnail_url` is the first variant whose path includes `/thumbnail` or `/small`; falls back to `public_url` if no such variant exists.

---

## Upload Endpoint Behavior

**Existing endpoint (unchanged signature):**

```
POST /api/gallery/albums/<slug>/media/
Authorization: Staff session required
Content-Type: multipart/form-data
```

### When Cloudflare is configured (both env vars set)

1. File is validated by `MediaItemWriteSerializer` as before (size ≤ 10 MB, allowed MIME type)
2. Pillow reads dimensions from in-memory bytes
3. File is POSTed to Cloudflare Images API
4. `MediaItem` is saved with:
   - `provider = 'cloudflare_images'`
   - `provider_public_id = <Cloudflare image ID>`
   - `public_url = <Cloudflare variant URL>`
   - `thumbnail_url = <Cloudflare variant URL>`
   - `original_file = None` (not stored locally)
   - `width`, `height`, `file_size` populated from in-memory bytes

### When Cloudflare is NOT configured (env vars absent)

Existing behavior is unchanged:
- `provider = 'local'`
- `original_file` saved to `gallery/originals/`
- `width`, `height`, `file_size` populated by `MediaItem._populate_local_image_metadata()`

### On Cloudflare upload failure

Returns `HTTP 502 Bad Gateway`:
```json
{
  "detail": "Cloudflare Images API error (HTTP 400)."
}
```

The Cloudflare API token is **not** included in the error message.

---

## Serializer Changes

`MediaItemWriteSerializer` now includes four additional read-only response fields:

| Field | Source |
|---|---|
| `provider` | `MediaItem.provider` — e.g. `"cloudflare_images"` or `"local"` |
| `public_url` | `MediaItem.public_url` — Cloudflare delivery URL |
| `thumbnail_url` | `MediaItem.thumbnail_url` — Cloudflare variant URL |
| `provider_public_id` | `MediaItem.provider_public_id` — Cloudflare image ID |

These are read-only — they cannot be set by staff via the API. They are populated by `perform_create` for Cloudflare uploads, or by the model for local uploads.

---

## Migration Created

`gallery/migrations/0007_alter_mediaitem_provider.py`

- Adds `'cloudflare_images'` to `MediaItem.PROVIDER_CHOICES`
- No SQL schema change (choices are application-level only for `CharField`)
- Auto-generated by `python manage.py makemigrations gallery`

---

## Commands Run and Results

```
python manage.py makemigrations gallery
```
→ Created `gallery/migrations/0007_alter_mediaitem_provider.py`

```
python manage.py check
```
→ `System check identified no issues (0 silenced).`

```
python manage.py migrate
```
→ `Applying gallery.0007_alter_mediaitem_provider... OK`

```
python manage.py test --verbosity=2
```
→ `Ran 44 tests in 38.678s OK` — all 44 tests pass (9 auth + 35 gallery)

---

## What Was Intentionally Not Touched

- No frontend files
- No JWT/token auth
- No video upload (`cloudflare_stream`) — model already had the choice; no upload logic added
- No `cloudinary` upload logic — model had the choice; no upload logic added
- No AI translation
- No thumbnail generation logic beyond using Cloudflare's built-in variants
- No Django admin customization
- No change to public read endpoints (`GET /albums/`, `GET /albums/<slug>/`, `GET /albums/<slug>/media/`)
- No orphan file cleanup (same as prior phases)

---

## Existing Serializer URL Resolution

`_get_public_url(obj, request)` and `_get_thumbnail_url(obj, request)` in `serializers.py` already handle non-local providers correctly:

```python
def _get_public_url(obj, request):
    if obj.provider == 'local':
        return _resolve_local_url(obj.original_file, request)
    return obj.public_url   # ← used for cloudflare_images
```

No serializer URL logic was changed — `cloudflare_images` provider falls through to `obj.public_url` and `obj.thumbnail_url` which are now populated by the service.

---

## Follow-up Work

1. **Add `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_IMAGES_API_TOKEN` to `.env`** before testing uploads in development. Generate the token in the Cloudflare dashboard with `Cloudflare Images: Edit` permission.

2. **Variant configuration.** Cloudflare returns the variant URLs defined for the account. Create a `thumbnail` or `small` named variant in the Cloudflare Images dashboard if a smaller variant is needed (the service picks it automatically by URL substring).

3. **Replace existing local media.** Currently local and Cloudflare items coexist. A future migration task could re-upload existing local media to Cloudflare. Out of scope for this phase.

4. **Cloudflare `requireSignedURLs`.** If the Cloudflare Images account is set to require signed URLs, the `public_url` alone won't work — signed URL generation would need to be added. For MVP, keep public delivery (unsigned URLs).

5. **Delete from Cloudflare on `DELETE /api/gallery/media/<pk>/`.** Currently deleting a `MediaItem` with `provider='cloudflare_images'` only deletes the DB row. The Cloudflare image is orphaned. A `post_delete` signal or service call to `DELETE /client/v4/accounts/{account_id}/images/v1/{image_id}` should be added in a future phase.

6. **Frontend upload form.** Backend contract is now defined. Frontend can POST multipart to `POST /api/gallery/albums/<slug>/media/` with `credentials: "include"` and `X-CSRFToken` header. The response includes `provider`, `public_url`, and `thumbnail_url`.
