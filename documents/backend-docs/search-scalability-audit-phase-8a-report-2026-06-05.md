# Search Scalability Audit Phase 8A Report

## Summary

Audit-only phase. No code changes were made. All findings are derived from
`gallery/views.py` and `gallery/models.py` as they exist at the time of this
audit. The audit covers every `icontains` search in public and admin endpoints,
the fields searched, join behaviour, current index coverage, and a recommendation
on whether `pg_trgm` GIN indexes are justified now.

---

## Search Endpoints Audited

### 1. `GET /api/gallery/albums/` — legacy `AlbumListCreateView`

**Fields searched (7 via Q OR):**

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search) |
Q(tags__name_bs__icontains=search) |
Q(tags__name_en__icontains=search) |
Q(tags__slug__icontains=search)
```

**Joins:** M2M join on `Album.tags` (Tag). `.distinct()` is applied.

**Risk:** Tags join produces a cross-product before deduplication. As tag
assignments grow this can return many duplicate rows before `.distinct()` reduces
them.

---

### 2. `GET /api/public/videos/` — `PublicVideoListView`

**Fields searched (4 via Q OR):**

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search)
```

**Joins:** None. `.distinct()` is applied because tag filtering elsewhere in the
view can be combined with search.

**Risk:** Low. Four `icontains` clauses on a single table. Pagination is cursor-
based with `page_size` capped at 50, so the DB never returns an unbounded result.
This is the highest-volume public endpoint.

---

### 3. `GET /api/public/albums/` — `PublicAlbumListView`

**Fields searched (4 via Q OR):**

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search)
```

**Joins:** None for search. `.distinct()` applied for tag filter.

**Risk:** Low. No join during search. Cursor-paginated.

---

### 4. `GET /api/gallery/admin/videos/` — `AdminVideoItemListView`

**Fields searched (11 via Q OR):**

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search) |
Q(cloudflare_uid__icontains=search) |
Q(album__title_bs__icontains=search) |
Q(album__title_en__icontains=search) |
Q(album__slug__icontains=search) |
Q(tags__name_bs__icontains=search) |
Q(tags__name_en__icontains=search) |
Q(tags__slug__icontains=search)
```

**Joins:** FK join on `album` (single row per video, no duplication). M2M join
on `VideoClip.tags` (Tag). `.distinct()` is applied.

**Risk:** Medium. Tags join is the concern. Admin-only, page-number paginated at
100 max — this limits rows returned but the DB still must evaluate the full
`WHERE` clause before pagination.

---

### 5. `GET /api/gallery/admin/images/` — `AdminImageItemListCreateView`

**Fields searched (13 via Q OR):**

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(title__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search) |
Q(alt_text_bs__icontains=search) |
Q(alt_text_en__icontains=search) |
Q(caption_bs__icontains=search) |
Q(caption_en__icontains=search) |
Q(provider_public_id__icontains=search) |
Q(album__title_bs__icontains=search) |
Q(album__title_en__icontains=search) |
Q(album__slug__icontains=search)
```

**Joins:** FK join on `album`. No M2M join (`MediaItem.tags` is a JSONField, not
relational). `.distinct()` is NOT applied (correctly omitted).

**Risk:** Medium. 13 `icontains` clauses is the highest per-endpoint count in the
codebase, but all on indexed-friendly columns and no M2M fan-out. Admin-only.

---

## Current Index Coverage

From `gallery/models.py`:

### `VideoClip` — explicit composite indexes

```python
models.Index(
    fields=['is_public', 'status', '-created_at', '-id'],
    name='video_pub_status_created_idx',
)
models.Index(
    fields=['album', 'is_public', 'status', '-created_at', '-id'],
    name='video_album_public_created_idx',
)
```

These indexes cover the public filter predicates (`is_public`, `status`) and
cursor ordering. They do **not** cover `icontains` search (which requires full-
text or trigram indexes).

### `VideoTimestampComment` — explicit indexes

```python
models.Index(fields=['video', 'status'])
models.Index(fields=['status'])
models.Index(fields=['created_at'])
```

The `['video', 'status']` index covers the approved-comments filter on every
`GET /api/public/videos/<pk>/comments/` request.

### `VisitorMessage` — explicit indexes

```python
models.Index(fields=['status'])
models.Index(fields=['created_at'])
models.Index(fields=['sender_email'])
```

### `Album`, `MediaItem`, `FieldNote`, `Tag` — no explicit search indexes

Django's default auto-primary-key `BigAutoField` index is present; no other
explicit indexes exist on these models' text fields.

---

## Assessment: Is `pg_trgm` Justified Now?

### Short answer: **No — not yet.**

### Reasoning

**Data volume is low.** The project is described as potentially reaching
thousands of videos in future, but no evidence of current scale problem exists.
`icontains` with B-tree indexes degrades noticeably only above ~100,000 rows per
table. At the current scale, query latency from `icontains` is dominated by
network round-trip time, not DB CPU.

**Public search is narrow.** `PublicVideoListView` searches only 4 fields on a
single table with no joins. Cursor pagination limits result set size. This is the
highest-traffic search path and it is already the least expensive.

**Admin search is admin-only.** The wider `icontains` queries (11 fields on
video, 13 on images) are only reachable by staff users. Admin endpoints are used
infrequently at low concurrency. Even moderately expensive queries are acceptable
here.

**`pg_trgm` adds deployment complexity.** Adding trigram indexes requires:

1. `CREATE EXTENSION IF NOT EXISTS pg_trgm;` — a PostgreSQL superuser privilege
   not always available on Heroku shared plans.
2. A new migration using `django.contrib.postgres` — which imports
   `django.contrib.postgres.indexes.GinIndex` and makes the migration
   incompatible with SQLite local development.
3. Index maintenance overhead on every write to the indexed column.

None of this complexity is justified at current scale.

---

## Recommended Future Trigger Points

Consider adding `pg_trgm` when **any** of the following is true:

1. `VideoClip` row count exceeds ~50,000 rows **and** users report slow
   `/api/public/videos/?search=` responses.
2. Admin video search query time (logged via `django.db.backends` slow-query
   logging at `DEBUG=True`) regularly exceeds 200ms.
3. Heroku Postgres performance tier is already at Standard-0 or higher (which
   grants `pg_trgm` extension privileges by default).

---

## Fields To Index First (When Justified)

Priority order, highest value first:

| Model | Field | Rationale |
|---|---|---|
| `VideoClip` | `title_bs` | Most common bilingual primary-language search |
| `VideoClip` | `title_en` | Fallback language |
| `Album` | `title_bs` | Album search in public and admin video/image endpoints |
| `Album` | `title_en` | Fallback |

**Fields to defer or skip:**

- `description_bs`, `description_en` — large text fields; GIN index cost high,
  benefit low (users rarely search by full description)
- `alt_text_*`, `caption_*` — admin-only; low volume
- `provider_public_id` — single admin use; already short fixed-format string

---

## What Was Not Changed

No code was modified in this phase. No migrations were created.
