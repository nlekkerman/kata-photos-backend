# Public Video Indexes Phase 2A Report

## Summary

Added two composite indexes to `VideoClip.Meta.indexes` to support the
cursor-paginated public video list endpoints added in Phase 1. One migration
was created. All 151 gallery tests pass. No other files were changed.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/models.py` | Added `indexes` list to `VideoClip.Meta` with two composite indexes |
| `gallery/migrations/0015_videoclip_public_indexes.py` | New migration adding both indexes |

---

## Indexes Added

### `video_pub_status_created_idx`

```python
models.Index(
    fields=['is_public', 'status', '-created_at', '-id'],
    name='video_pub_status_created_idx',
)
```

Supports the main public cursor-browsing path:

```sql
WHERE is_public = TRUE AND status = 'ready'
ORDER BY created_at DESC, id DESC
```

### `video_album_public_created_idx`

```python
models.Index(
    fields=['album', 'is_public', 'status', '-created_at', '-id'],
    name='video_album_public_created_idx',
)
```

Supports album-filtered public browsing (`?album=<pk>`):

```sql
WHERE album_id = X AND is_public = TRUE AND status = 'ready'
ORDER BY created_at DESC, id DESC
```

**Name length note:** The originally recommended name
`video_public_status_created_idx` is 31 characters, exceeding Django's
30-character index name limit (`models.E034`). The name was shortened to
`video_pub_status_created_idx` (28 characters) to pass the system check.
`video_album_public_created_idx` is exactly 30 characters and passes as-is.

---

## Migration Created

```
gallery/migrations/0015_videoclip_public_indexes.py
```

- Depends on `0014_visitor_message_replied_at_reply_model`
- Contains only two `AddIndex` operations
- No model field changes, no data migrations

---

## Why These Indexes

The `PublicVideoListView` (Phase 1) queries:

```python
VideoClip.objects.select_related('album').filter(
    is_public=True,
    status=VideoClip.STATUS_READY,
).order_by('-created_at', '-id')
```

Without an index, this requires a full table scan plus sort. As the
`VideoClip` table grows, this becomes expensive. The composite index on
`(is_public, status, -created_at, -id)` allows PostgreSQL to satisfy the
`WHERE` clause and the cursor `ORDER BY` from a single index scan with no
additional sort step.

The album composite index covers the `?album=<pk>` filter path:

```python
qs.filter(album_id=pk)
```

Adding `album_id` as the leading column means album-filtered public browsing
also avoids a sort step.

The existing `cloudflare_uid` unique index was not touched. The existing FK
index on `album_id` is superseded for public browsing by the composite index
(PostgreSQL will prefer the composite index for the filtered+ordered query).

---

## What Was Not Changed

- `gallery/serializers.py` — not touched
- `gallery/views.py` — not touched
- `gallery/public_urls.py` — not touched
- `gallery/tests.py` — not touched
- `config/settings.py` — not touched
- No model field changes
- No admin endpoints modified
- No album endpoints modified
- No tag indexes added
- No search indexes added
- No caching added
- No `published_at` index added
- No custom managers added

---

## Validation Results

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery
# Ran 151 tests in 62.316s
# OK
```

- 151 tests run, 151 pass, 0 failures, 0 errors

---

## Next Recommended Step

**Phase 2B — Tag and search index (optional)**

The `?tag=<slug>` and `?search=<q>` filter paths were not indexed in this
phase. A partial `GinIndex` on the `title_bs`/`title_en` columns (using
PostgreSQL `pg_trgm`) would support the `icontains` search filter efficiently
at scale. This requires the `django.contrib.postgres` app and is a separate
migration with no model field changes.
