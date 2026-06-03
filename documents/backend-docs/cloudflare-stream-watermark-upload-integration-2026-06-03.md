# Cloudflare Stream Watermark Upload Integration
**Date:** 2026-06-03  
**Scope:** Backend only — gallery app

---

## Summary

Watermark UID integration for Cloudflare Stream direct-upload was already partially
implemented across `settings.py`, `cloudflare_stream.py`, and the admin-side
`AdminVideoDirectUploadView`. However, the original public `VideoClipDirectUploadView`
(routed at `videos/direct-upload/`) was missing the `watermark_uid` variable
assignment, causing a `NameError` at runtime. This task:

1. Fixed the missing assignment in `VideoClipDirectUploadView`.
2. Added 7 automated tests covering watermark forwarding, no-watermark path,
   permission enforcement, record creation, and Cloudflare rejection handling.

---

## Files Changed

| File | Lines changed (approx) | Change type |
|------|------------------------|-------------|
| `gallery/views.py` | +1 | Bug fix — add missing `watermark_uid` assignment |
| `gallery/tests.py` | +115 | Added two test classes (7 new tests) |

**Total changed lines: ~116**  
Well within the 50–200 line target.

---

## Current Cloudflare Upload Method

**Direct Creator Upload (TUS)**  
Endpoint: `POST /accounts/{account_id}/stream/direct_upload`  
The backend requests a one-time TUS upload URL from Cloudflare and returns it to
the client. The client pushes the video file directly to Cloudflare via that URL.
The backend never handles the video bytes.

---

## Where Watermark UID Is Attached

`gallery/services/cloudflare_stream.py` — `create_direct_upload()`:

```python
if watermark_uid:
    body["watermark"] = {"uid": watermark_uid}
```

This adds `"watermark": {"uid": "<UID>"}` to the JSON body sent to the Cloudflare
Direct Upload API. Cloudflare burns the watermark profile into every transcoded
rendition of the uploaded video.

---

## Env Variable Used

```
CLOUDFLARE_STREAM_WATERMARK_UID=29b0fa37be907b876f3c5670cfaf8890
```

Read in `config/settings.py`:

```python
CLOUDFLARE_STREAM_WATERMARK_UID = os.getenv("CLOUDFLARE_STREAM_WATERMARK_UID", "")
```

Read in both upload views:

```python
watermark_uid = getattr(settings, "CLOUDFLARE_STREAM_WATERMARK_UID", "")
```

---

## Behavior When Watermark UID Is Missing

**Env var absent / empty string:**  
`watermark_uid` resolves to `""`. The `if watermark_uid:` guard in
`create_direct_upload()` skips adding `"watermark"` to the request body.
Upload proceeds without a watermark. This is consistent with the existing
project pattern for optional Cloudflare settings
(e.g. `CLOUDFLARE_IMAGES_API_TOKEN` defaults to `""`).

**Cloudflare rejects a non-empty but invalid UID:**  
`create_direct_upload()` raises `CloudflareStreamError`. The view catches it and
returns `HTTP 502 Bad Gateway` with the Cloudflare error codes in the response
detail. No `VideoClip` record is created. The error is logged server-side
(without the API token).

---

## Bug Found and Fixed

`VideoClipDirectUploadView.post` (the view served at
`/api/gallery/videos/direct-upload/`) was passing `watermark_uid=watermark_uid`
to `create_direct_upload()` but never assigned the variable — a dormant
`NameError` that would have caused HTTP 500 on every video upload attempt.

**Fix (1 line added to `gallery/views.py`):**

```python
# Before (missing line):
expiry_seconds = settings.CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
# watermark_uid not defined here — NameError at runtime

# After:
expiry_seconds = settings.CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
watermark_uid = getattr(settings, "CLOUDFLARE_STREAM_WATERMARK_UID", "")
```

`AdminVideoDirectUploadView` (at `/api/gallery/admin/…`) already had the correct
assignment and was unaffected.

---

## New Tests Added (`gallery/tests.py`)

### `VideoClipDirectUploadWatermarkTests` (6 tests)
Settings override: `CLOUDFLARE_STREAM_WATERMARK_UID = "29b0fa37be907b876f3c5670cfaf8890"`

| Test | Assertion |
|------|-----------|
| `test_watermark_uid_forwarded_to_cloudflare` | `watermark_uid` kwarg equals the configured UID |
| `test_direct_upload_creates_videoclip_record` | One `VideoClip` created with correct UID and `STATUS_UPLOADING` |
| `test_response_includes_upload_url` | Response contains `upload_url` for TUS upload |
| `test_anonymous_cannot_request_upload` | 401/403 returned; `create_direct_upload` not called |
| `test_non_staff_cannot_request_upload` | 401/403 returned; `create_direct_upload` not called |
| `test_cloudflare_rejection_surfaces_as_502` | `CloudflareStreamError` → HTTP 502; no DB record created |

### `VideoClipDirectUploadNoWatermarkTests` (1 test)
Settings override: `CLOUDFLARE_STREAM_WATERMARK_UID = ""`

| Test | Assertion |
|------|-----------|
| `test_empty_watermark_uid_not_forwarded` | `watermark_uid=""` is passed (no watermark field in Cloudflare payload) |

---

## Commands Run

```
python manage.py check
# → System check identified no issues (0 silenced)

python manage.py test gallery
# → Ran 42 tests in ~37s  OK
# (35 pre-existing + 7 new)
```

---

## Validation Results

| Check | Result |
|-------|--------|
| `manage.py check` | 0 issues |
| Pre-existing tests (35) | All pass |
| New watermark tests (7) | All pass |
| Total | **42 / 42 OK** |

---

## Manual Test Steps

1. Start the backend:  
   ```
   python manage.py runserver
   ```

2. Authenticate as a staff user via the admin or session API.

3. POST to `/api/gallery/videos/direct-upload/` with:
   ```json
   {"title_bs": "Test Video", "max_duration_seconds": 300}
   ```

4. Confirm the response contains `upload_url` and `video.cloudflare_uid`.

5. Upload a test video file to `upload_url` using a TUS client (e.g. tus-js-client
   or the Cloudflare Stream dashboard upload widget).

6. Wait for Cloudflare to finish processing (poll `/api/gallery/videos/<pk>/sync/`
   until `status` is `"ready"`).

7. Play the video — the watermark profile `29b0fa37be907b876f3c5670cfaf8890`
   should be burned into the video.

8. Verify that videos uploaded **before** this change do not have a watermark
   (Cloudflare does not retroactively apply watermarks to existing videos).

---

## Edge Cases Documented

| Edge case | Handling |
|-----------|----------|
| Existing videos (uploaded before this change) | **No watermark.** Must be re-uploaded to receive watermark. Cloudflare does not retroactively apply watermark profiles. |
| New uploads after this change | Watermark burned in during Cloudflare transcoding. |
| `CLOUDFLARE_STREAM_WATERMARK_UID` not set | Upload proceeds without watermark (consistent with other optional Cloudflare settings). |
| Cloudflare rejects the watermark UID | `HTTP 502` returned; no DB record created; error logged server-side. |

---

## What Was Not Touched

- **Frontend files:** untouched.
- **Image upload logic** (`cloudflare_images.py`, `MediaItemWriteSerializer`): untouched.
- **`AdminVideoDirectUploadView`:** watermark already correctly implemented; untouched.
- **Database migrations:** no schema changes required.
- **`VideoClipSyncView`**, **`VideoClipListView`**, **`VideoClipDetailView`**: untouched.
- No fake frontend overlay watermarks added.
- No clean-original / private-download architecture added.
- No fallback upload paths added.
