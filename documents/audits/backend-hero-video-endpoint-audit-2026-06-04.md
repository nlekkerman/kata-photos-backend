# Backend Hero Video Endpoint Audit — 2026-06-04

## Summary

`GET /api/public/hero-video/` returns HTTP 404 because it requires a `VideoClip` record with **both** `is_public=True` **and** `status='ready'`. The upload flow sets `is_public=False` (default) and `status='uploading'` at creation. The admin must manually set `is_public=True` via the Django admin UI or PATCH API, **and** must explicitly trigger a refresh-status call to advance the status from `uploading` → `processing` → `ready`. Neither step is automatic. If either condition is not met, the endpoint returns 404.

---

## Endpoint Implementation

| Item | Value |
|------|-------|
| URL route | `api/public/hero-video/` registered in `gallery/public_urls.py` line 6 |
| Included from | `config/urls.py` line 13: `path("api/public/", include("gallery.public_urls"))` |
| View | `HeroVideoView` in `gallery/views.py` line 796 |
| Serializer | `HeroVideoSerializer` in `gallery/serializers.py` line 859 |
| Auth | `AllowAny` — no authentication required |

### Exact query (gallery/views.py lines 807–813)

```python
video = (
    VideoClip.objects
    .select_related('album')
    .filter(is_public=True, status=VideoClip.STATUS_READY)
    .order_by('-created_at')
    .first()
)
if video is None:
    return Response(status=status.HTTP_404_NOT_FOUND)
```

The view returns `404` if no matching record exists.

---

## Eligibility Rules

A `VideoClip` must satisfy **all** of the following to appear in the hero endpoint:

| Field | Required value | Model default |
|-------|---------------|---------------|
| `is_public` | `True` | `False` |
| `status` | `'ready'` | `'uploading'` |

**No album-level filtering** is applied. The `album` FK is optional (`null=True, blank=True`). `select_related('album')` is used only for serialization; there is no `album__is_published` filter.

There is **no** `is_featured`, `is_hero`, `show_on_homepage`, or `placement` field on `VideoClip`.

### Fields returned by HeroVideoSerializer

`id`, `title_bs`, `title_en`, `album_id`, `album_title_bs`, `album_title_en`, `duration_seconds`, `cloudflare_uid`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`.

---

## Admin Upload Flow

### Step 1 — Direct upload creation

`POST /api/gallery/admin/videos/direct-upload/` (`AdminVideoDirectUploadView`, views.py line 588)

Creates a `VideoClip` with:
- `status = VideoClip.STATUS_UPLOADING` (`'uploading'`) — **hardcoded**
- `is_public` — **not set**, takes model default of `False`

Returns a one-time Cloudflare TUS upload URL to the frontend.

### Step 2 — Mark upload complete (optional intermediate step)

`POST /api/gallery/admin/videos/complete-upload/` (`AdminVideoCompleteUploadView`, views.py line 656)

Transitions `status` from `'uploading'` → `'processing'`.  
Does **not** contact Cloudflare.  
Does **not** set `is_public`.

### Step 3 — Refresh status from Cloudflare

`POST /api/gallery/admin/videos/<pk>/refresh-status/` (`AdminVideoRefreshStatusView`, views.py line 710)  
Alias: `POST /api/gallery/videos/<pk>/sync/` (`VideoClipSyncView`, views.py line 271)

Calls `get_video_details()` from `gallery/services/cloudflare_stream.py`.  
Runs `map_cloudflare_status(cf)` and saves new `status`, `duration_seconds`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`.

**This is the only path to set `status='ready'`.** It must be triggered explicitly by the admin/frontend after Cloudflare finishes processing.

### Step 4 — Publish the video (manual)

`PATCH /api/gallery/admin/videos/<pk>/` with `{"is_published": true}`

`AdminVideoItemWriteSerializer` maps `is_published` → `is_public` (serializers.py line 780).  
`is_published` / `is_public` are **never set automatically** at any point in the upload flow.

---

## Cloudflare Ready/Sync Flow

There is **no webhook**, **no Celery task**, **no Django signal**, **no management command**, and **no periodic job** that automatically syncs Cloudflare status.

The only ways `status` advances to `'ready'`:

1. Admin calls `POST /api/gallery/admin/videos/<pk>/refresh-status/`
2. Admin calls `POST /api/gallery/videos/<pk>/sync/`
3. Admin edits the `status` field directly in the Django admin UI (field is not `readonly` — it appears in the `('Album / Publishing', {'fields': ('album', 'status', 'is_public')})` fieldset in `gallery/admin.py` line 104).

`map_cloudflare_status()` logic (`cloudflare_stream.py` lines ~115–132):

```
readyToStream == True  → 'ready'
status.state == "ready" → 'ready'
status.state == "error" → 'failed'
otherwise              → 'processing'
```

---

## Most Likely Cause

**Two independent gates both default to blocking:**

1. **`is_public` defaults to `False`** — the video was never explicitly published via PATCH or Django admin.
2. **`status` defaults to `'uploading'`** and only advances to `'ready'` when the admin explicitly calls the refresh-status endpoint after Cloudflare finishes processing.

Either (or both) fields being in their default state causes the query `filter(is_public=True, status='ready')` to return zero rows, producing HTTP 404.

---

## Evidence

| Finding | Source |
|---------|--------|
| `HeroVideoView` query filters `is_public=True, status='ready'` | `gallery/views.py` lines 807–813 |
| `VideoClip.is_public` default is `False` | `gallery/models.py` line 213 |
| `VideoClip.status` default is `'uploading'` | `gallery/models.py` line 212 |
| Direct-upload view hardcodes `status=VideoClip.STATUS_UPLOADING` | `gallery/views.py` line 219 |
| Direct-upload view does not set `is_public` | `gallery/views.py` lines 215–222 |
| `is_public` is only set via PATCH `AdminVideoItemWriteSerializer` | `gallery/serializers.py` lines 780, 793 |
| `status` only advances to `'ready'` via explicit refresh-status call | `gallery/views.py` lines 710–790 |
| No webhook / signal / celery / cron for automatic sync | Full grep of `gallery/` — no matches for `webhook`, `signal`, `celery`, `periodic`, `cron`, `schedule` in implementation files |

---

## Suggested Non-Destructive Data Checks

### Local Django shell

```python
from gallery.models import VideoClip

# Inspect all videos
list(VideoClip.objects.values(
    "id", "title_bs", "album_id", "is_public", "status",
    "cloudflare_uid", "cloudflare_playback_url", "created_at"
))

# Count eligible videos (must return >= 1 for hero endpoint to work)
VideoClip.objects.filter(is_public=True, status='ready').count()

# Check what is blocking each video
VideoClip.objects.values("id", "title_bs", "is_public", "status")
```

### Heroku production shell

```bash
heroku run python manage.py shell --app kata-wild-backend
```

Then run the same queries above.

---

## Recommended Fix Direction

No code changes are required if the issue is purely data/workflow:

1. **Confirm Cloudflare has finished processing** — the video's `readyToStream` flag must be `true` in the Cloudflare dashboard.
2. **Call refresh-status** to pull the `'ready'` status into the Django record:
   ```
   POST /api/gallery/admin/videos/<pk>/refresh-status/
   ```
3. **Publish the video** — set `is_public=True`:
   ```
   PATCH /api/gallery/admin/videos/<pk>/
   { "is_published": true }
   ```
   Or toggle `is_public` to `True` directly in the Django admin.

If the workflow should be less manual, the fix direction would be:
- Auto-set `is_public=True` on the first successful `'ready'` sync (optional, in `AdminVideoRefreshStatusView` / `VideoClipSyncView`).
- Or add a webhook endpoint that Cloudflare calls when processing completes.

---

## Files That Would Need Changing Later

If automatic publishing/status is desired (not required now):

| File | Purpose |
|------|---------|
| `gallery/views.py` | Add auto-publish logic in `AdminVideoRefreshStatusView.post()` or `VideoClipSyncView.post()` |
| `gallery/urls.py` | Add webhook URL if a Cloudflare webhook handler is added |
| `gallery/views.py` | New `CloudflareWebhookView` handler |
| `config/settings.py` | Add `CLOUDFLARE_STREAM_WEBHOOK_SECRET` if webhook verification is needed |

---

## Audit Status

Complete. Source-derived only. No code changed. No data modified.
