# Public Video Pagination Phase 1 Report

## Summary

Implemented a clean, cursor-paginated public video browsing API contract at
`GET /api/public/videos/` and `GET /api/public/videos/<pk>/`.

Changes are narrow and additive. No existing endpoints, models, or unrelated
code was touched. All 151 gallery tests pass.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `PublicVideoCardSerializer` and `PublicVideoDetailSerializer` |
| `gallery/views.py` | Added `CursorPagination` import, `PublicVideoCursorPagination`, `PublicVideoListView`, `PublicVideoDetailView`; imported new serializers |
| `gallery/public_urls.py` | Registered two new URL patterns; added view imports |
| `gallery/tests.py` | Added `PublicVideoListAPITests` (13 tests) and `PublicVideoDetailAPITests` (12 tests) |

No migrations, no model changes, no frontend files changed.

---

## API Contract Added

### `GET /api/public/videos/`

```
/api/public/videos/?cursor=&page_size=12&album=&tag=&search=&lang=bs
```

- Anonymous access allowed (`AllowAny`)
- Filters on `is_public=True` and `status='ready'` at the database level
- Cursor pagination, default 12 items, max 50
- Consistent newest-first ordering via `('-created_at', '-id')`
- Supports `album=<pk>`, `tag=<slug>`, `search=<query>`, `lang=bs|en`
- Uses `select_related('album')`; no `prefetch_related` (card serializer does not return tags)
- No Cloudflare API calls during request

**Response shape** (DRF cursor pagination):
```json
{
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Bosanski Naslov",
      "album_id": 5,
      "album_title": "Album BS",
      "cloudflare_uid": "abc123",
      "cloudflare_thumbnail_url": "https://...",
      "duration_seconds": 120,
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

### `GET /api/public/videos/<pk>/`

```
/api/public/videos/42/?lang=bs
```

- Anonymous access allowed
- Returns 404 for private, uploading, processing, failed, or missing videos
- Uses `select_related('album').prefetch_related('tags')`

**Response shape**:
```json
{
  "id": 42,
  "title": "Naslov na bosanskom",
  "description": "Opis na bosanskom",
  "album_id": 5,
  "album_title": "Album BS",
  "cloudflare_uid": "abc123",
  "cloudflare_thumbnail_url": "https://...",
  "cloudflare_playback_url": "https://...",
  "duration_seconds": 120,
  "tags": [{"id": 1, "name_bs": "Ptice", "name_en": "Birds", "slug": "ptice"}],
  "created_at": "2026-06-01T10:00:00Z"
}
```

---

## Serializer Changes

Two new serializers added at the bottom of `gallery/serializers.py`:

**`PublicVideoCardSerializer`** — list endpoint only:
- Exposes: `id`, `title`, `album_id`, `album_title`, `cloudflare_uid`, `cloudflare_thumbnail_url`, `duration_seconds`, `created_at`
- `title` resolved via `resolve_translated(obj, 'title', lang)` — returns single language string
- `album_id` uses `obj.album_id` (direct FK column, `None`-safe)
- `album_title` resolved via `resolve_translated` with fallback to `album.title`
- Does NOT expose `title_bs`, `title_en`, `description_bs`, `description_en`, `status`, `is_public`, `updated_at`, or any admin field

**`PublicVideoDetailSerializer`** — detail endpoint only:
- Adds `description` (language-aware), `cloudflare_playback_url`, and `tags` (via `TagSerializer`)
- Same language resolution and field exclusion policy as the card serializer
- No admin-only fields exposed

Both serializers reuse the existing `resolve_translated` helper and `TagSerializer` already present in the codebase.

---

## Frontend Notes

### 1. Description Source

Use `description` from the public video detail response.

Important:

- `PublicVideoCardSerializer` does not include description.
- `PublicVideoDetailSerializer` includes language-resolved `description`.
- Do not use raw `description_bs` / `description_en` on public frontend because public detail already resolves language.
- Do not change backend serializer shape.
- If current player only has card data, fetch the detail endpoint before rendering the banner.

---

## Pagination Behavior

`PublicVideoCursorPagination` added to `gallery/views.py`:

```python
class PublicVideoCursorPagination(CursorPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50
    ordering = ('-created_at', '-id')
```

- `ordering = ('-created_at', '-id')` provides stable cursor ordering (avoids ties on `created_at` via secondary sort on `id`)
- Applied per-view via `pagination_class` — no global pagination setting changed
- DRF cursor pagination shape: `{"next": "...", "previous": "...", "results": [...]}`

---

## Filters Implemented

| Parameter | Behavior |
|---|---|
| `album=<pk>` | `filter(album_id=pk)` — database-level |
| `tag=<slug>` | `filter(tags__slug=slug).distinct()` — database-level |
| `search=<q>` | `icontains` on `title_bs`, `title_en`, `description_bs`, `description_en` — database-level, `.distinct()` |
| `lang=bs\|en` | Resolved by existing `LangContextMixin`; defaults to `en` if omitted |

The search filter on the list endpoint does NOT search album title or tag names (unlike the legacy `/api/gallery/videos/` endpoint). This keeps the new endpoint minimal and its contract clear.

---

## Tests Added

25 new tests in `gallery/tests.py`, split into two classes:

### `PublicVideoListAPITests` (13 tests)
1. `test_anonymous_can_list_videos` — 200 for unauthenticated request
2. `test_returns_only_public_ready_videos` — private + non-ready excluded
3. `test_excludes_private_videos` — `is_public=False` hidden
4. `test_excludes_non_ready_statuses` — uploading/processing/failed hidden
5. `test_response_is_paginated` — response has `results` and `next` keys
6. `test_page_size_respected` — `?page_size=5` returns 5 items
7. `test_page_size_capped_at_max` — `?page_size=100` returns ≤ 50 items
8. `test_album_filter` — `?album=<pk>` filters correctly
9. `test_tag_filter` — `?tag=<slug>` filters correctly
10. `test_search_filter` — `?search=` filters by title
11. `test_lang_bs_returns_bosnian_title` — `?lang=bs` returns `title_bs`
12. `test_response_does_not_include_raw_title_fields` — card does not expose heavy fields
13. `test_response_includes_expected_card_fields` — all required card fields present

### `PublicVideoDetailAPITests` (12 tests)
1. `test_anonymous_can_retrieve_public_ready_video` — 200 for valid public video
2. `test_returns_404_for_private_video`
3. `test_returns_404_for_uploading_video`
4. `test_returns_404_for_processing_video`
5. `test_returns_404_for_failed_video`
6. `test_returns_404_for_missing_video`
7. `test_detail_includes_expected_fields` — all required detail fields present
8. `test_detail_does_not_include_admin_fields` — heavy fields absent
9. `test_detail_lang_bs_returns_bosnian_title` — `?lang=bs` resolves correct title and description
10. `test_detail_album_id_and_title_correct` — album FK and resolved album title correct
11. `test_detail_tags_returned` — tags list populated correctly
12. `test_detail_video_without_album_returns_none_album_id` — null album handled safely

---

## Validation Results

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery
# Ran 151 tests in 60.455s
# OK
```

- 126 pre-existing tests: all pass (no regression)
- 25 new tests: all pass

---

## What Was Not Changed

- `gallery/models.py` — no model or field changes
- `config/settings.py` — no global REST_FRAMEWORK pagination added
- `gallery/urls.py` — legacy `/api/gallery/videos/` endpoints untouched
- Admin endpoints — not modified
- Album endpoints — not modified
- Upload lifecycle — not modified
- Cloudflare webhook/sync code — not modified
- Frontend files — not modified
- No database migrations created

---

## Next Recommended Step

**Phase 2 — Database indexes for the public video list**

Add composite indexes on `(is_public, status, created_at DESC, id DESC)` on
`VideoClip` to support the cursor-paginated list query efficiently at scale.
This requires only a migration (no code changes) and is safe to add after the
Phase 1 contract has been validated in production.
