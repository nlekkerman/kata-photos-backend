# Cloudflare Stream — Video Sync & Playback API
**Date:** 2026-06-01  
**Phase:** Stream Sync & Playback (post-upload)

---

## Files Changed

| File | Change |
|---|---|
| `gallery/services/cloudflare_stream.py` | Extended: added helpers, status mapping, read API functions |
| `gallery/views.py` | Extended: added `VideoClipListView`, `VideoClipDetailView`, `VideoClipSyncView` |
| `gallery/urls.py` | Extended: registered 3 new URL patterns |

Total: 3 files changed. No migrations required (model already had all needed fields).

---

## Endpoints Added

### `GET /api/gallery/videos/`
Public/admin video list.

- **Public users:** returns only `is_public=True` and `status='ready'` clips.
- **Staff/admin users:** returns all clips regardless of status or visibility.
- **Optional filter:** `?album=<pk>` filters by album ID.

### `GET /api/gallery/videos/<pk>/`
Single video detail with same visibility rules as the list.

### `POST /api/gallery/videos/<pk>/sync/`
Staff-only sync endpoint.

1. Loads the local `VideoClip` by PK.
2. Calls Cloudflare `GET /accounts/{id}/stream/{uid}` to fetch live metadata.
3. Updates: `status`, `duration_seconds`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`.
4. Only writes changed fields (`update_fields`).
5. Returns the updated serialized `VideoClip`.

---

## Service Changes (`cloudflare_stream.py`)

### Error class rename
`CloudflareStreamUploadError` renamed to `CloudflareStreamError` (more general).  
`CloudflareStreamUploadError` kept as a backward-compat alias — no existing imports break.

### New helpers

| Function | Purpose |
|---|---|
| `_safe_get(url, token, timeout)` | Internal: performs a GET request, raises `CloudflareStreamError` on failure. Token never included in error messages. |
| `_check_configured(account_id, api_token)` | Internal: raises if credentials are missing. |
| `build_playback_url(*, customer_subdomain, uid)` | Returns `https://{subdomain}/{uid}/iframe` |
| `build_thumbnail_url(*, customer_subdomain, uid)` | Returns `https://{subdomain}/{uid}/thumbnails/thumbnail.jpg` |
| `map_cloudflare_status(cf_result)` | Maps Cloudflare response dict to local status string (see below) |
| `get_video_details(*, account_id, api_token, uid)` | Calls `GET /stream/{uid}`, returns `result` dict |
| `list_videos(*, account_id, api_token)` | Calls `GET /stream`, returns list of `result` dicts |

---

## Cloudflare Response Fields Used

From `GET /accounts/{id}/stream/{uid}`:

| CF Field | Used for |
|---|---|
| `readyToStream` | Primary indicator that video is playable |
| `status.state` | Secondary status: `pendingupload`, `inprogress`, `ready`, `error` |
| `duration` | Float seconds; stored as rounded integer in `duration_seconds` |

Fields intentionally ignored: `meta`, `thumbnail` (from CF response — we generate our own), `playback.hls`, `playback.dash`, `preview`, `watermark`, `allowedOrigins`, signed URLs.

---

## Status Mapping

| Cloudflare condition | Local `VideoClip.status` |
|---|---|
| `readyToStream == true` | `ready` |
| `status.state == "ready"` | `ready` |
| `status.state == "error"` | `failed` |
| `status.state == "inprogress"` | `processing` |
| `status.state == "pendingupload"` | `processing` |
| unknown / empty state, not ready | `processing` |

The `uploading` status is only set at creation time (`VideoClipDirectUploadView`) and is never returned by `map_cloudflare_status`. This is correct: once sync is called, the file has left the browser.

---

## Playback URL Format

```
https://{CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN}/{cloudflare_uid}/iframe
```

Example:
```
https://customer-abc123.cloudflarestream.com/a1b2c3d4e5f6/iframe
```

This is the Cloudflare Stream iframe embed URL. It requires no signed token for public videos. Source: Cloudflare Stream docs — [Embed videos](https://developers.cloudflare.com/stream/viewing-videos/using-the-stream-player/).

---

## Thumbnail URL Format

```
https://{CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN}/{cloudflare_uid}/thumbnails/thumbnail.jpg
```

Example:
```
https://customer-abc123.cloudflarestream.com/a1b2c3d4e5f6/thumbnails/thumbnail.jpg
```

This matches the documented Cloudflare Stream thumbnail pattern. Source: [Displaying thumbnails](https://developers.cloudflare.com/stream/viewing-videos/displaying-thumbnails/).

---

## Serializer (`VideoClipSerializer`)

Already complete from Phase 4. Exposes all required fields:

```
id, album, title_bs, title_en, description_bs, description_en,
cloudflare_uid, cloudflare_thumbnail_url, cloudflare_playback_url,
duration_seconds, status, is_public, created_at, updated_at
```

`cloudflare_uid`, `cloudflare_thumbnail_url`, `cloudflare_playback_url`, `status` are read-only.

---

## Admin

`VideoClipAdmin` was already registered and complete from Phase 4 (confirmed in `gallery/admin.py`). Supports editing `status`, `is_public`, title/description fields. Cloudflare fields are read-only in the admin.

---

## Commands Run

```
python manage.py check
# → System check identified no issues (0 silenced).

python manage.py test --verbosity=2
# → Ran 44 tests in 38.15s — OK
```

No migrations needed. All existing tests pass.

---

## What Was Intentionally Not Implemented

- **Webhooks** — Not in scope for this phase.
- **Delete/cleanup** — Not in scope.
- **Signed URLs / private videos** — Not implemented; all playback URLs are public iframe links.
- **HLS / custom player** — iframe embed only for MVP.
- **Bulk sync** — No `POST /api/gallery/videos/sync-all/` endpoint; sync is per-video only.
- **Automatic sync on upload** — No post-upload polling or background task.
- **Cloudflare `thumbnail` field from API response** — We generate our own thumbnail URL from the customer subdomain rather than using whatever CF returns in the response, for consistency and predictability.

---

## Frontend Contract (Next Phase)

### List videos
```
GET /api/gallery/videos/
GET /api/gallery/videos/?album=<pk>
```
Response: array of `VideoClip` objects.

### Single video
```
GET /api/gallery/videos/<pk>/
```

### Trigger sync (admin/staff only, requires session auth)
```
POST /api/gallery/videos/<pk>/sync/
```
Response: updated `VideoClip` object.

### VideoClip shape
```json
{
  "id": 1,
  "album": 2,
  "title_bs": "Naslov",
  "title_en": "Title",
  "description_bs": "",
  "description_en": "",
  "cloudflare_uid": "abc123",
  "cloudflare_thumbnail_url": "https://customer-xxx.cloudflarestream.com/abc123/thumbnails/thumbnail.jpg",
  "cloudflare_playback_url": "https://customer-xxx.cloudflarestream.com/abc123/iframe",
  "duration_seconds": 42,
  "status": "ready",
  "is_public": true,
  "created_at": "2026-06-01T14:20:00Z",
  "updated_at": "2026-06-01T15:00:00Z"
}
```

### Playback (iframe embed)
```html
<iframe
  src="https://customer-xxx.cloudflarestream.com/{uid}/iframe"
  allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
  allowfullscreen
></iframe>
```
