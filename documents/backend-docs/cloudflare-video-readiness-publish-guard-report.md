# Cloudflare Video Readiness Publish Guard — Implementation Report

**Date:** 2026-06-08
**Repository:** `kata-photos-backend`
**Scope:** Backend only — no frontend files modified

---

## Files Changed

| File | Change |
|---|---|
| `gallery/services/cloudflare_stream.py` | Tightened `map_cloudflare_status` — require both `readyToStream` AND `status.state == "ready"` |
| `gallery/views.py` | Fixed `VideoClipDirectUploadView` and `AdminVideoDirectUploadView` — create with `is_public=False` |
| `gallery/serializers.py` | Tightened publish guard in `AdminVideoItemWriteSerializer.validate()` — added playback/thumbnail URL checks |
| `gallery/serializers.py` | Added `can_publish` computed field to `AdminVideoItemSerializer` |

---

## Bug Found

### Bug 1 — Videos exposed publicly before encoding was complete

**Location:** `gallery/views.py` — `VideoClipDirectUploadView` (line ~252) and `AdminVideoDirectUploadView` (line ~819)

Both `VideoClip.objects.create(...)` calls passed `is_public=True` at upload time, while `status` was still `'uploading'`. This meant every newly created video was immediately visible in public-facing endpoints (`/api/public/albums/<slug>/videos/`, hero video, album cover) even before Cloudflare had received the file, let alone encoded it.

**Fix:** Both create calls now pass `is_public=False`.

---

### Bug 2 — `map_cloudflare_status` marked ready from thumbnail availability alone

**Location:** `gallery/services/cloudflare_stream.py` — `map_cloudflare_status()`

The previous logic returned `"ready"` when `readyToStream=True`, without also confirming `status.state == "ready"`. Cloudflare sets `readyToStream=True` (making the thumbnail endpoint work) before all encoding variants and the DASH/HLS manifests finish generating. This caused:

```
GET https://customer-....cloudflarestream.com/<uid>/manifest/video.mpd
→ 500 Internal Server Error
```

The iframe and thumbnail loaded successfully (thumbnail available), but the actual video playback manifest was not yet ready.

**Fix:** Status is now set to `"ready"` only when **both** conditions are true:
- `readyToStream == true`
- `status.state == "ready"`

This matches Cloudflare's own documentation guidance for confirming full playback readiness.

---

### Bug 3 — Publish guard did not check playback/thumbnail URLs

**Location:** `gallery/serializers.py` — `AdminVideoItemWriteSerializer.validate()`

The existing guard checked `status == 'ready'` before allowing `is_published=True`, but it did not verify that `cloudflare_playback_url` and `cloudflare_thumbnail_url` were non-empty. A video could pass the status check while still missing its playback URL (e.g. if sync was never run, or sync ran before `customer_subdomain` was configured).

**Fix:** The guard now additionally rejects publish if either URL field is empty.

---

## Exact Cloudflare Fields Used for Readiness

| Cloudflare API field | Path in response dict | Used for |
|---|---|---|
| `readyToStream` | `result.readyToStream` | Boolean — thumbnail available (not sufficient alone) |
| `status.state` | `result.status.state` | String — `"ready"` confirms full encoding complete |

Only when `readyToStream == true` **and** `status.state == "ready"` is `VideoClip.status` set to `"ready"`.

---

## New Readiness Rule

```
Cloudflare readyToStream=False OR status.state != "ready"  →  VideoClip.status = "processing"
Cloudflare readyToStream=True  AND status.state == "ready" →  VideoClip.status = "ready"
Cloudflare status.state == "error"                         →  VideoClip.status = "failed"
```

The sync endpoint and admin refresh-status endpoint both call `map_cloudflare_status()`, so both are fixed by the single change to that function.

---

## Publish Guard Rule

`AdminVideoItemWriteSerializer.validate()` rejects `is_published=True` unless all three conditions pass:

1. `instance.status == "ready"`
2. `instance.cloudflare_playback_url` is non-empty
3. `instance.cloudflare_thumbnail_url` is non-empty

Error response on violation:

```json
{"is_published": "Video još nije spreman za objavu."}
```

HTTP 400. No Cloudflare-internal error codes are exposed.

---

## `can_publish` Field Added

`AdminVideoItemSerializer` now includes a computed boolean field:

```json
{
  "can_publish": true
}
```

**Rule:**

```
can_publish = (
    status == "ready"
    AND is_public == False
    AND cloudflare_playback_url != ""
    AND cloudflare_thumbnail_url != ""
)
```

`can_publish` is `false` for already-published videos (`is_public=True`), so the frontend can safely use it to enable/disable the "Objavi" button without additional logic.

---

## Edge Cases Handled

| Edge case | Behaviour |
|---|---|
| Upload just requested, file not sent yet | `status='uploading'`, `is_public=False` — not visible |
| File uploaded, Cloudflare processing | `status='processing'`, `is_public=False` — not visible |
| `readyToStream=True` but `state != "ready"` (manifest not ready) | `status='processing'` — publish blocked |
| Cloudflare `state == "error"` | `status='failed'`, `is_public` forced to `False` by sync |
| Publish clicked while processing | Rejected: `"Video još nije spreman za objavu."` |
| Publish clicked on failed video | Rejected: same 400 |
| Publish clicked on already-published video | `can_publish=false`; PATCH with `is_published=true` is a no-op (no state change) |
| Duplicate publish clicks | Idempotent — second request is a no-op |
| Playback URL missing (sync not yet run) | Publish blocked by URL guard |
| Thumbnail URL missing | Publish blocked by URL guard |
| Missing UID | Video was never created — not applicable at publish time |

---

## What Was Intentionally Not Touched

- `VideoClip` model — no changes
- Migrations — none added or required
- Public video endpoints — filter logic (`is_public=True, status='ready'`) unchanged
- Hero video endpoint — unchanged
- Album cover resolution (`_resolve_album_cover`) — unchanged
- Frontend files — not touched
- Cloudflare API request logic (`get_video_details`, `create_direct_upload`) — unchanged
- `VideoClipCompleteUploadView` / `AdminVideoCompleteUploadView` — unchanged (correctly sets `status='processing'`, never touches `is_public`)
- `VideoClipSerializer` (legacy/public) — unchanged

---

## Commands Run

```
& c:\Users\nlekk\kata-photos-backend\.venv\Scripts\python.exe manage.py check
→ System check identified no issues (0 silenced).
```

No test suite run. No migrations applied.

---

## Validation Result

`python manage.py check` passed with 0 issues after all changes.

---

## Confirmation

- **No frontend files were modified.**
- **No models were modified.**
- **No migrations were added.**
- **No auto-publish logic was added.**
- **No fake readiness or fallback paths were added.**
