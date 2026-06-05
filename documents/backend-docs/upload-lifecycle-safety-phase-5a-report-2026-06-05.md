# Upload Lifecycle Safety Phase 5A Report

## Summary

Phase 5A makes the video upload lifecycle safer and more deliberate before the
project scales to hundreds or thousands of videos.

Two bugs were corrected (both legacy and admin `direct-upload` views created
`VideoClip` records with `is_public=True` at upload time) and three safety
rules were added (failed status forces `is_public=False`, ready status never
auto-publishes, admin cannot set `is_public=True` unless `status=ready`).

13 new backend tests were added covering every required rule. All 242 gallery
tests pass with no regressions.

No model schema changes were required. No migrations were added.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/views.py` | Fix legacy + admin direct-upload `is_public=True` → `False`; add failed-status forces `is_public=False` to both sync views |
| `gallery/serializers.py` | Add `validate()` guard on `AdminVideoItemWriteSerializer` — rejects `is_published=True` when `status` is not `ready` |
| `gallery/tests.py` | Update one existing assertion; add `AdminUploadLifecycleSafetyTests` (13 tests) |
| `documents/backend-docs/upload-lifecycle-safety-phase-5a-report-2026-06-05.md` | This report |

---

## Upload Flow Before

```
POST /api/gallery/admin/videos/direct-upload/
  → VideoClip created with status=uploading, is_public=True   ← UNSAFE

POST /api/gallery/videos/direct-upload/ (legacy)
  → VideoClip created with status=uploading, is_public=True   ← UNSAFE

POST /api/gallery/admin/videos/complete-upload/
  → status: uploading → processing
  → is_public: unchanged (True from direct-upload step)        ← UNSAFE

POST /api/gallery/admin/videos/<pk>/refresh-status/
  → status: updated from Cloudflare (ready / processing / failed)
  → is_public: never forced to False even on failed            ← UNSAFE

POST /api/gallery/videos/<pk>/sync/ (legacy)
  → same as above                                              ← UNSAFE

PATCH /api/gallery/admin/videos/<pk>/
  → is_published accepted regardless of current status         ← UNSAFE
```

---

## Upload Flow After

```
POST /api/gallery/admin/videos/direct-upload/
  → VideoClip created with status=uploading, is_public=False   ✓

POST /api/gallery/videos/direct-upload/ (legacy)
  → VideoClip created with status=uploading, is_public=False   ✓

POST /api/gallery/admin/videos/complete-upload/
  → status: uploading → processing
  → is_public: remains False                                    ✓

POST /api/gallery/admin/videos/<pk>/refresh-status/
  → Cloudflare ready: status=ready, is_public remains False until admin publishes
  → Cloudflare error: status=failed, is_public forced to False  ✓

POST /api/gallery/videos/<pk>/sync/ (legacy)
  → same as above                                               ✓

PATCH /api/gallery/admin/videos/<pk>/
  → is_published=True accepted only when status=ready
  → otherwise HTTP 400: "Video must be ready before it can be published."  ✓
```

---

## Safety Rules Implemented

### Rule 1 — New uploads are private by default
`VideoClip` is created with `is_public=False` in both `VideoClipDirectUploadView`
(legacy) and `AdminVideoDirectUploadView`. Previously both set `is_public=True`.

### Rule 2 — Complete upload does not publish
`AdminVideoCompleteUploadView` only changes `status` from `uploading` to
`processing`. It never touches `is_public`. This was already the behaviour; no
change was needed beyond verifying (confirmed by test 4).

### Rule 3 — Refresh to failed forces is_public=False
Both `VideoClipSyncView` (legacy) and `AdminVideoRefreshStatusView` now include:
```python
if new_status == VideoClip.STATUS_FAILED and video.is_public:
    video.is_public = False
    update_fields.append('is_public')
```
A previously-public video that transitions to `failed` is automatically hidden.

### Rule 4 — Ready status does not auto-publish
Refresh to `ready` updates `status` only. `is_public` is not touched; an admin
must explicitly PATCH `is_published=True` after confirming the video is ready.

---

## Admin Publish Guard

`AdminVideoItemWriteSerializer.validate()` was extended:

```python
def validate(self, data):
    wants_public = data.get('is_public')  # mapped from is_published
    if wants_public is True:
        current_status = getattr(self.instance, 'status', None)
        if current_status != VideoClip.STATUS_READY:
            raise serializers.ValidationError(
                {'is_published': 'Video must be ready before it can be published.'}
            )
    return data
```

This rejects PATCH attempts with `is_published=True` when `status` is
`uploading`, `processing`, or `failed`, returning HTTP 400 with a clear message.

---

## Tests Added Or Updated

### Updated
- `VideoClipDirectUploadWatermarkTests.test_direct_upload_creates_videoclip_record`:
  Changed `assertTrue(clip.is_public)` → `assertFalse(clip.is_public)` to match
  the new private-by-default behaviour.

### Added: `AdminUploadLifecycleSafetyTests` (13 tests)

| # | Test name | Rule |
|---|---|---|
| 1 | `test_admin_direct_upload_creates_video_with_status_uploading` | Rule 1 |
| 2 | `test_admin_direct_upload_creates_video_with_is_public_false` | Rule 1 |
| 3 | `test_complete_upload_moves_status_to_processing` | Rule 2 |
| 4 | `test_complete_upload_does_not_set_is_public_true` | Rule 2 |
| 5 | `test_refresh_status_ready_updates_status` | Rule 4 |
| 6 | `test_refresh_status_ready_does_not_auto_publish` | Rule 4 |
| 7 | `test_refresh_status_failed_sets_status_failed` | Rule 3 |
| 8 | `test_refresh_status_failed_forces_is_public_false` | Rule 3 |
| 9 | `test_admin_cannot_publish_video_while_uploading` | Publish guard |
| 10 | `test_admin_cannot_publish_video_while_processing` | Publish guard |
| 11 | `test_admin_cannot_publish_video_while_failed` | Publish guard |
| 12 | `test_admin_can_publish_video_when_ready` | Publish guard |
| 13 | `test_public_list_excludes_non_ready_and_private_videos` | Public endpoint unchanged |

---

## Validation Results

```
python manage.py check
  → System check identified no issues (0 silenced).

python manage.py test gallery
  → Found 242 test(s).
  → Ran 242 tests in 104.574s
  → OK
```

No failures. No regressions. All 13 new tests pass.

---

## Backward Compatibility Notes

**Breaking change for existing uploads in the field:**

Before Phase 5A, every new `direct-upload` request immediately produced a
`VideoClip` with `is_public=True`. If the frontend admin UI was relying on
newly-created videos being public by default, videos will now appear as hidden
until admin explicitly sets `is_published=True` after the video is ready.

This is the intended behaviour. The frontend admin UI should be updated to:
1. Show videos with `is_published=False` clearly as "Draft / Not published".
2. Show a "Publish" button that is only active when `status=ready`.
3. Handle the new `HTTP 400` response when attempting to publish a non-ready video.

Previously-created `VideoClip` records that were `is_public=True` with
`status=ready` are not affected.

---

## What Was Not Changed

- `gallery/models.py` — no model or schema changes required.
- `gallery/migrations/` — no new migrations.
- `gallery/services/cloudflare_stream.py` — `map_cloudflare_status` was
  inspected and correct; no changes needed.
- Public endpoints (`/api/public/videos/`, `/api/public/videos/<pk>/`,
  `/api/public/hero-video/`) — filtering logic unchanged.
- No Cloudflare webhooks added.
- No scheduled jobs or caching added.
- No bulk-refresh UI or provider asset deletion.
- No frontend files.

---

## Frontend Follow-Up Required

The admin video UI (frontend) should be updated in a follow-up phase to:

1. **Show `is_published=False` as "Draft"** — Videos with `status=uploading`,
   `status=processing`, and `is_public=False` should be clearly labelled as
   not yet public.
2. **Show `status=failed` with a warning** — Failed videos should be visually
   distinct and the admin should see that `is_published` was forced to `False`.
3. **Publish button gating** — The publish toggle/button should be disabled
   (or absent) unless `status=ready`.
4. **Handle HTTP 400 on publish attempt** — Show the message
   `"Video must be ready before it can be published."` if the API rejects
   the request (defense in depth against direct API calls).

---

## Scalability Notes

- New uploads are not publicly visible at any point before admin publishes them.
- Failed videos cannot remain publicly visible: `is_public` is forced to `False`
  on any sync/refresh that returns `status=failed`.
- `status=ready` and `is_public=True` are intentionally separate states. A video
  being `ready` on Cloudflare does not mean it is published; admin approval is
  required.
- Public endpoints (`/api/public/videos/`) still enforce `is_public=True AND
  status=ready` — this has not changed.
- No frontend files were changed in this phase.
- No Cloudflare webhook was added in this phase.

---

## Next Recommended Step

**Phase 5B (Frontend):** Update the admin video management UI to:
- Reflect the new private-by-default behaviour.
- Gate the publish toggle on `status=ready`.
- Show clear draft/failed/processing states.
- Display the 400 validation error when publish is attempted too early.
