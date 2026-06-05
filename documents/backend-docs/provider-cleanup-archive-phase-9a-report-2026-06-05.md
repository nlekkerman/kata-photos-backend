# Provider Cleanup / Archive Phase 9A Report

## Summary

Audit-only phase. No code changes were made. All findings are derived from
`gallery/views.py`, `gallery/models.py`, `gallery/admin.py`, and
`gallery/services/` as they exist at the time of this audit.

---

## What DELETE Currently Does

### `DELETE /api/gallery/admin/videos/<pk>/`

Implemented via `AdminVideoItemRetrieveUpdateDestroyView`, which inherits
`generics.RetrieveUpdateDestroyAPIView` with no `perform_destroy` override.

**Effect:** Calls Django ORM `.delete()` on the `VideoClip` instance. This
removes only the Django database record. The docstring in `views.py` explicitly
states:

```python
# Note: DELETE removes only the Django record. Cloudflare Stream asset is NOT
# automatically deleted. Use the Cloudflare dashboard or API for that.
```

**Provider asset:** The Cloudflare Stream video file (`cloudflare_uid`) remains
alive after a Django-side DELETE. There is no post-delete signal, no task queue
call, and no service call to `cloudflare_stream` that removes the asset.

**Cascade:** `VideoClip` has FK relationships:
- `VisitorMessage.video` — `on_delete=SET_NULL`. Visitor messages are preserved
  with `video=NULL` after the clip is deleted.
- `VideoTimestampComment.video` — `on_delete=CASCADE`. All comments for the
  clip are deleted from the DB with it.
- `Album.videos` (reverse relation via FK `VideoClip.album`) — the album record
  is not affected.

---

### `DELETE /api/gallery/admin/images/<pk>/`

Implemented via `AdminImageItemRetrieveUpdateDestroyView`, which inherits
`generics.RetrieveUpdateDestroyAPIView` with no `perform_destroy` override.

**Effect:** Calls Django ORM `.delete()` on the `MediaItem` instance. Removes
only the DB record.

**Local provider:** If `provider='local'` and `original_file` is set, the file
on disk (`MEDIA_ROOT/gallery/originals/…`) is **not** deleted. Django does not
automatically delete `FileField`/`ImageField` backing files on model deletion.
The file becomes an orphan on disk.

**Cloudflare Images provider:** If `provider='cloudflare_images'`, the image
asset referenced by `provider_public_id` remains in Cloudflare Images. There is
no post-delete signal or service call to Cloudflare Images.

**Cascade:** `MediaItem` has FK relationships:
- `Album.cover_media` — `on_delete=SET_NULL`. Albums whose cover was this item
  will have `cover_media=NULL` after deletion.
- `FieldNote.cover_image` — `on_delete=SET_NULL`. Field notes whose cover was
  this item will have `cover_image=NULL`.

---

### `DELETE /api/gallery/admin/image-galleries/<id>/`

Implemented via `AdminImageGalleryRetrieveUpdateDestroyView`.

**Cascade:** `Album` is the parent of `MediaItem` via
`MediaItem.album` (`on_delete=CASCADE`). Deleting an Album cascades to all its
`MediaItem` records at the DB level. All local files and Cloudflare Images
assets referenced by those items are orphaned (same reasoning as above).

---

### `DELETE /api/gallery/admin/video-galleries/<id>/`

**Cascade:** `VideoClip.album` is a nullable FK (`on_delete=SET_NULL`). Deleting
a video Album does NOT cascade-delete `VideoClip` records; it sets
`VideoClip.album=NULL` on all clips in that gallery. Cloudflare Stream assets
are unaffected.

---

## Failed Upload Records

`VideoClip` records created by `AdminVideoDirectUploadView` start with
`status='uploading'`. If the client never calls `complete-upload` (crash, tab
close, network failure), the record remains `status='uploading'` indefinitely.

If Cloudflare transcoding fails, `refresh-status` will set `status='failed'`
and `is_public=False`. The `VideoClip` DB record remains permanently with no
automatic expiry or cleanup.

**Current situation:** Failed and stale-uploading records accumulate. There is
no:
- Automatic expiry mechanism
- Management command to identify them
- Admin action to bulk-clean them
- Soft-archive field

---

## Soft Archive / Unpublish

`VideoClip` uses `is_public` (boolean) as the publish/unpublish control.
Setting `is_public=False` hides the clip from public endpoints but keeps it
in the DB. This is the de-facto soft-hide mechanism.

`MediaItem` uses `is_published` (boolean) the same way.

Neither model has a dedicated `is_archived` or `archived_at` field. The
existing admin `VisitorMessage.STATUS_ARCHIVED` is the only example of an
archived state in the codebase, and it is only for messages.

---

## Orphaned Provider Asset Risk Summary

| Provider | Delete action | Asset cleanup |
|---|---|---|
| Cloudflare Stream | Django record deleted | **No** — asset remains in CF |
| Cloudflare Images | Django record deleted | **No** — asset remains in CF |
| `local` | Django record deleted | **No** — file remains on disk |
| Cascade (image gallery delete) | All MediaItem records deleted | **No** — all orphaned |

---

## Recommended Future Cleanup Approach

### Narrow / Safe Next Steps (Not Implemented Here)

The following are safe to implement in a future focused phase:

**1. Management command: list orphan candidates**

A read-only `python manage.py list_orphan_uploads` command that prints
`VideoClip` records matching:
- `status='uploading'` and `created_at < now - 2 hours`
- `status='failed'`

No DB writes. Output only. Safe in production.

**2. Management command: safe stale-upload cleanup**

A `python manage.py clean_stale_uploads --dry-run / --confirm` command that
deletes `VideoClip` records matching:
- `status='uploading'` and `created_at < now - 24 hours`
- `is_public=False`

Must require explicit `--confirm` flag. Must never touch `status='ready'` or
`is_public=True` records.

**3. Provider-aware delete for local files**

Override `perform_destroy` on `AdminImageItemRetrieveUpdateDestroyView` to call
`instance.original_file.delete(save=False)` when `provider='local'` before
calling `super().perform_destroy()`. This is a 3-line change with minimal risk.

**4. Cloudflare Stream DELETE on video record deletion**

Override `perform_destroy` on `AdminVideoItemRetrieveUpdateDestroyView` to call
`cloudflare_stream.delete_video(uid=instance.cloudflare_uid)`. Requires
implementing a `delete_video` function in `gallery/services/cloudflare_stream.py`.
This is higher-risk (network call in the HTTP request cycle) and should be a
separate explicit phase with:
- Retry/error handling (delete from DB even if CF call fails, with a warning)
- An explicit admin confirmation step
- Tests that mock the CF API

**5. Cloudflare Images DELETE on media item deletion**

Same pattern as (4) but for `cloudflare_images.delete_image(cf_id=…)`.

---

## What Was Not Changed

No code was modified in this phase. No migrations were created.
