# Cloudflare Stream Burned-in Watermark — Implementation Report

**Date:** 2026-06-03  
**Scope:** Backend-only  
**Task:** Attach a Cloudflare Stream watermark profile UID to every new video direct upload

---

## Files Changed

| File | Change summary | Approx. changed lines |
|------|---------------|----------------------|
| `config/settings.py` | Added `CLOUDFLARE_STREAM_WATERMARK_UID` setting | +4 |
| `gallery/services/cloudflare_stream.py` | Added `watermark_uid` parameter to `create_direct_upload` | +7 |
| `gallery/views.py` | Read setting and pass `watermark_uid` in both upload views | +4 (+4) |

**Total changed lines: ~19** (well within the soft cap of 300).

---

## Current Cloudflare Upload Method Found

**Method:** Cloudflare Stream **Direct Creator Upload** (TUS protocol)  
**API endpoint:** `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/stream/direct_upload`  
**Service function:** `gallery/services/cloudflare_stream.py` → `create_direct_upload()`  
**Called from two views:**
- `gallery/views.py` → `VideoClipDirectUploadView.post()` (public admin API)
- `gallery/views.py` → `AdminVideoDirectUploadView.post()` (custom admin API)

The Direct Creator Upload API supports a `watermark` object in the JSON request body. Cloudflare's expected shape:

```json
{
  "watermark": { "uid": "<watermark_profile_uid>" }
}
```

---

## Exact Place Where Watermark UID Is Attached

`gallery/services/cloudflare_stream.py`, inside `create_direct_upload()`:

```python
if watermark_uid:
    body["watermark"] = {"uid": watermark_uid}
```

This block is placed after the existing `meta` check and before the API request is made.

---

## Environment Variable Added

```env
CLOUDFLARE_STREAM_WATERMARK_UID=
```

Added to `config/settings.py`:

```python
# Optional: burned-in watermark profile UID applied to every new direct upload.
# Leave empty to upload without a watermark.
CLOUDFLARE_STREAM_WATERMARK_UID = os.getenv("CLOUDFLARE_STREAM_WATERMARK_UID", "")
```

---

## Behavior When Watermark UID Is Missing

**Decision: skip watermark silently** — consistent with all other optional Cloudflare settings in this codebase (`CLOUDFLARE_STREAM_API_TOKEN`, `CLOUDFLARE_IMAGES_API_TOKEN`, etc.), which use `os.getenv("VAR", "")` and let callers handle the empty-string case.

- If `CLOUDFLARE_STREAM_WATERMARK_UID` is **set**: watermark profile is included in the upload request; Cloudflare burns the watermark into the processed video.
- If `CLOUDFLARE_STREAM_WATERMARK_UID` is **empty or unset**: upload proceeds normally without a watermark. No error is raised.
- If Cloudflare rejects the watermark UID (e.g. invalid UID): the existing `CloudflareStreamError` is raised with the HTTP error code, propagated by the view as `HTTP 502`, and logged with the full response body. No silent failure.

---

## Existing Videos

Existing already-uploaded videos are **not affected**. They were uploaded without a watermark. To apply the watermark they must be **re-uploaded** through the admin upload flow after `CLOUDFLARE_STREAM_WATERMARK_UID` is configured.

---

## Architecture Decisions

- **No clean-original/private-download architecture added.** If a clean unwatermarked copy is needed, it must be handled manually outside the app (e.g. original file shared via email, Drive, or WeTransfer).
- **No frontend fake watermark overlay added.**
- **No public download button added.**
- **Image upload logic was not touched.** Only `cloudflare_stream.py` was modified; `cloudflare_images.py` was not changed.
- **No fallback upload paths added.**
- **No mock/fake backend behavior added.**

---

## Commands Run

```
python manage.py check
python manage.py test gallery
```

---

## Validation Results

```
System check identified no issues (0 silenced).
...................................
----------------------------------------------------------------------
Ran 35 tests in 29.826s
OK
```

All 35 existing tests pass. No new tests were added (no test file was changed).

---

## What Was Not Touched

- `gallery/services/cloudflare_images.py` — image upload, unchanged
- `gallery/models.py` — no model changes required
- `gallery/serializers.py` — unchanged
- `gallery/migrations/` — no migrations required
- `auth_api/` — unchanged
- `gallery/tests.py` — unchanged
- Any frontend file — none exist in this repository
- `VideoClipSyncView`, `VideoClipListView`, `VideoClipDetailView`, `VideoClipCompleteUploadView` — unchanged
