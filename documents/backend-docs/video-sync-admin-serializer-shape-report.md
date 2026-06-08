# Video Sync Endpoint — Admin Serializer Shape Fix

**Date:** 2026-06-08  
**Scope:** Backend only — `gallery/views.py`  
**Task:** Make `VideoClipSyncView` return the same serializer shape as the admin video list/detail endpoint.

---

## Investigation Findings

### 1. Sync endpoint inspected

- **Route:** `POST /api/gallery/videos/<int:pk>/sync/`
- **View class:** `VideoClipSyncView` (`gallery/views.py`, line 321)
- **Previous return:** `Response(VideoClipSerializer(video).data)`

### 2. Serializer previously used

`VideoClipSerializer` — fields exposed:

```
id, album, title_bs, title_en, description_bs, description_en,
cloudflare_uid, cloudflare_thumbnail_url, cloudflare_playback_url,
duration_seconds, status, is_public, tags, created_at, updated_at
```

Key issues:
- Exposes `is_public` (model name), **not** `is_published` (admin API name)
- Does **not** expose `can_publish`
- Does **not** expose `gallery_id`, `gallery_slug`, `gallery_title_bs`

### 3. Serializer now used

`AdminVideoItemSerializer` — fields exposed:

```
id, gallery_id, gallery_slug, gallery_title_bs,
title_bs, title_en, description_bs, description_en,
cloudflare_uid, cloudflare_thumbnail_url, cloudflare_playback_url,
duration_seconds, status, is_published, can_publish,
tags, created_at, updated_at
```

Mapping: `is_published = serializers.BooleanField(source="is_public", read_only=True)`  
Computed: `can_publish` → True when `status == "ready"` and `not is_public` and playback/thumbnail URLs set.

### 4. Does sync modify `is_public`?

**Yes — one intentional safety rule only:**

```python
# Safety: failed videos must not remain publicly visible.
if new_status == VideoClip.STATUS_FAILED and video.is_public:
    video.is_public = False
    update_fields.append('is_public')
```

This sets `is_public = False` **only** when Cloudflare reports a FAILED status and the video was somehow still public. This is a defensive guard, not auto-publish behavior. It was left unchanged.

### 5. Does sync auto-publish?

**No.** Sync never sets `is_public = True`. The only write to `is_public` inside the sync path is the FAILED-guard above (sets it to `False`).

### 6. Does sync mark videos ready only from strict Cloudflare rule?

**Yes.** Status is derived exclusively by `map_cloudflare_status(cf)` from `gallery/services/cloudflare_stream.py`, which maps the Cloudflare Stream state to backend status values. No status is promoted to `ready` outside this function.

### 7. Admin video list endpoint serializer

`AdminVideoItemListView` (`gallery/views.py`) has `serializer_class = AdminVideoItemSerializer` — confirmed as the source of truth for admin video shape.

---

## Change Made

**File:** `gallery/views.py`  
**Location:** `VideoClipSyncView.post`, final return statement

**Before:**
```python
return Response(VideoClipSerializer(video).data)
```

**After:**
```python
return Response(AdminVideoItemSerializer(video).data)
```

No other lines changed. `AdminVideoItemSerializer` was already imported at the top of `views.py`.

---

## Cloudflare Lifecycle Confirmation

The Cloudflare upload/status lifecycle was **not modified**:

```
uploading → processing → ready → manual publish
```

- Upload creates video with `is_public=False`, `status=uploading` ✓
- Cloudflare processing mapped via `map_cloudflare_status` ✓
- `status=ready` set only when Cloudflare confirms readiness ✓
- `is_public` is never set to `True` during upload, sync, or status refresh ✓
- Manual publish (`is_published` PATCH) is the only path to `is_public=True` ✓

---

## Expected Response Shape

**Ready, hidden video:**
```json
{
  "id": 19,
  "status": "ready",
  "is_published": false,
  "can_publish": true,
  "cloudflare_thumbnail_url": "https://...",
  "cloudflare_playback_url": "https://...",
  "gallery_id": 3,
  "gallery_slug": "...",
  "gallery_title_bs": "...",
  "tags": []
}
```

**Published video:**
```json
{
  "status": "ready",
  "is_published": true,
  "can_publish": false
}
```

---

## Validation

- `python manage.py check` → **System check identified no issues (0 silenced)**
- No migrations added
- No model fields changed
- No frontend files modified
- No public endpoint filters changed
- No Cloudflare readiness checks loosened
- Diff: 1 line changed (`VideoClipSerializer` → `AdminVideoItemSerializer` in the return statement)
