# Backend Video Upload Public Default Fix — 2026-06-04

## Summary

Both direct-upload video creation views now set `is_public=True` when creating a `VideoClip` record. Previously the field defaulted to `False`, meaning every uploaded video was silently blocked from the public hero-video endpoint until an admin manually published it. The fix is a one-line addition to each `VideoClip.objects.create()` call.

---

## Files Changed

| File | Change |
|------|--------|
| `gallery/views.py` | Added `is_public=True` to `VideoClip.objects.create()` in `VideoClipDirectUploadView.post()` (line ~213) |
| `gallery/views.py` | Added `is_public=True` to `VideoClip.objects.create()` in `AdminVideoDirectUploadView.post()` (line ~636) |
| `gallery/tests.py` | Added `self.assertTrue(clip.is_public)` to `test_direct_upload_creates_videoclip_record` in `VideoClipDirectUploadWatermarkTests` |

---

## What Changed

Before:

```python
video = VideoClip.objects.create(
    album=data.get('album'),
    title_bs=data['title_bs'],
    ...
    cloudflare_uid=cf_result['uid'],
    status=VideoClip.STATUS_UPLOADING,
)
```

After:

```python
video = VideoClip.objects.create(
    album=data.get('album'),
    title_bs=data['title_bs'],
    ...
    cloudflare_uid=cf_result['uid'],
    status=VideoClip.STATUS_UPLOADING,
    is_public=True,
)
```

Applied identically to both:
- `VideoClipDirectUploadView` (`POST /api/gallery/videos/direct-upload/`)
- `AdminVideoDirectUploadView` (`POST /api/gallery/admin/videos/direct-upload/`)

---

## Why This Was Needed

`GET /api/public/hero-video/` queries:

```python
VideoClip.objects.filter(is_public=True, status=VideoClip.STATUS_READY)
```

`VideoClip.is_public` defaults to `False` on the model. Nothing in the upload flow ever set it to `True` automatically. An admin had to manually PATCH the record or edit it in the Django admin after every upload. This was an undocumented friction point that caused the hero endpoint to return 404 even after Cloudflare finished processing a video.

Admin-uploaded videos are intended to be public. Setting `is_public=True` at creation removes the manual publish step while still requiring Cloudflare to confirm `status='ready'` before the video appears in the hero endpoint.

---

## Validation

```
python manage.py check          → System check identified no issues (0 silenced)
python manage.py test gallery --verbosity=2 → Ran 42 tests in 36.384s OK
```

All 42 tests passed including the updated `test_direct_upload_creates_videoclip_record` which now asserts:
- `clip.status == VideoClip.STATUS_UPLOADING`
- `clip.is_public == True`

---

## Commands Run

```bash
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test gallery --verbosity=2
```

---

## Deployment Notes

- No database migration required. `is_public` is an existing model field with a default; this change only affects the value passed at record creation, not the schema.
- Existing `VideoClip` records in production that were created before this fix remain `is_public=False` unless manually updated.
- Deploy by pushing the updated `gallery/views.py` to Heroku. No `heroku run migrate` needed.

---

## Frontend Impact

None. The frontend calls the direct-upload endpoint and uses the returned `upload_url` to push video data to Cloudflare. It does not depend on the `is_public` field value in the creation response. No frontend files were changed.

---

## Remaining Manual Step

Cloudflare status still must be refreshed/synced so the video can move from uploading/processing to ready. The hero endpoint still requires `status='ready'`.

After uploading, call:

```
POST /api/gallery/admin/videos/<pk>/refresh-status/
```

Once Cloudflare has finished processing and this endpoint confirms `status='ready'`, the video will automatically appear in `GET /api/public/hero-video/` without any further action.
