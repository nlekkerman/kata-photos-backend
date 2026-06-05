# Public Album Endpoints Phase 3A Report

## Summary

Added three dedicated public album endpoints under `/api/public/albums/`.
These provide a clean, canonical contract for frontend gallery browsing without
touching the legacy `/api/gallery/albums/` endpoints.

No model changes. No migrations. No caching. No search indexes.
Changes are confined to views, serializers, URLs, and tests.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `PublicAlbumCardSerializer`, `PublicAlbumDetailSerializer` |
| `gallery/views.py` | Added `PublicAlbumCursorPagination`, `PublicAlbumListView`, `PublicAlbumDetailView`, `PublicAlbumVideosView`; added `Exists`, `OuterRef` imports; added `PublicAlbumCardSerializer`, `PublicAlbumDetailSerializer` imports |
| `gallery/public_urls.py` | Wired three new URL patterns; added three new view imports |
| `gallery/tests.py` | Added 30 new tests across `PublicAlbumListAPITests`, `PublicAlbumDetailAPITests`, `PublicAlbumVideosAPITests` |

---

## API Contracts Added

### 1. Public album list

```
GET /api/public/albums/
    ?cursor=&page_size=12&type=video|image&tag=&search=&lang=bs|en&populated=true
```

- Anonymous access allowed
- Returns only `is_published=True` albums
- Cursor-paginated, default 12, max 50
- Supports `type`, `tag`, `search`, `populated`, `lang`, `page_size`

### 2. Public album detail

```
GET /api/public/albums/<slug>/
    ?lang=bs|en
```

- Anonymous access allowed
- Returns album metadata only — no nested video or media lists
- 404 for unpublished or missing albums

### 3. Public album videos

```
GET /api/public/albums/<slug>/videos/
    ?cursor=&page_size=12&lang=bs|en
```

- Anonymous access allowed
- 404 if album does not exist or is not published
- Returns only `is_public=True` + `status=ready` videos
- Cursor-paginated, default 12, max 50
- Uses `PublicVideoCardSerializer` from Phase 1

---

## Serializers Added Or Reused

### `PublicAlbumCardSerializer` (new)

Fields: `id`, `slug`, `title`, `description`, `gallery_type`, `display_order`, `cover`, `tags`

- `title` and `description` are language-resolved via `resolve_translated`
- `cover` uses the existing lightweight `MediaCoverSerializer` (thumbnail + alt_text only)
- `tags` uses the existing `TagSerializer`
- No raw bilingual fields. No admin fields. No nested video/media lists.

### `PublicAlbumDetailSerializer` (new)

Fields: `id`, `slug`, `title`, `description`, `seo_title`, `seo_description`, `gallery_type`, `display_order`, `cover`, `tags`, `created_at`

- All text fields are language-resolved
- No raw bilingual fields. No nested video/media lists.

### `PublicVideoCardSerializer` (reused from Phase 1)

Used unchanged for `GET /api/public/albums/<slug>/videos/`.

---

## Pagination Behavior

| Endpoint | Paginator | Default | Max | Ordering |
|---|---|---|---|---|
| `GET /api/public/albums/` | `PublicAlbumCursorPagination` | 12 | 50 | `display_order`, `id` |
| `GET /api/public/albums/<slug>/videos/` | `PublicVideoCursorPagination` (Phase 1, reused) | 12 | 50 | `-created_at`, `-id` |

Album list ordering uses `display_order` ascending with `id` as stable tie-breaker.
Video list ordering matches the Phase 1 public video list contract.

---

## Populated Album Logic

`populated=true` is implemented using database-level `Exists` subqueries
via Django `django.db.models.Exists` + `OuterRef`. No Python-level filtering.

For video albums (`gallery_type='video'`):

```python
Exists(VideoClip.objects.filter(
    album=OuterRef('pk'),
    is_public=True,
    status=VideoClip.STATUS_READY,
))
```

For image albums (`gallery_type='image'`):

```python
Exists(MediaItem.objects.filter(
    album=OuterRef('pk'),
    is_published=True,
    media_type='image',
))
```

The final filter is:

```python
Q(gallery_type='video', _has_ready_video=True) |
Q(gallery_type='image', _has_published_image=True)
```

An empty published album is excluded. An album with only private/non-ready
videos is excluded from `populated=true&type=video`.

---

## Filters Implemented

| Parameter | Behaviour |
|---|---|
| `type=video\|image` | Filters by `gallery_type` field |
| `tag=<slug>` | `filter(tags__slug=tag_slug).distinct()` |
| `search=<q>` | `icontains` on `title_bs`, `title_en`, `description_bs`, `description_en` |
| `populated=true` | Database `Exists` subquery as described above |
| `lang=bs\|en` | Passed via `LangContextMixin` to serializer context |
| `page_size` | Respected and capped at 50 |

---

## Tests Added

### `PublicAlbumListAPITests` — 14 tests

1. Anonymous user can list public albums
2. Unpublished albums are excluded
3. Response is paginated
4. `page_size` is respected
5. `page_size` is capped at 50
6. `lang=bs` returns Bosnian-resolved title and description
7. Raw bilingual/admin fields not exposed in list
8. `type=video` filters video albums
9. `type=image` filters image albums
10. `tag=` filters albums by tag slug
11. `search=` filters albums by title
12. `populated=true` excludes empty published albums
13. `populated=true&type=video` includes only albums with public-ready videos
14. `populated=true&type=image` includes only albums with published image media

### `PublicAlbumDetailAPITests` — 8 tests

1. Anonymous user can retrieve published album
2. Unpublished album returns 404
3. Missing album returns 404
4. `lang=bs` resolves title, description, seo_title
5. Detail includes all expected fields
6. Detail does not include nested video/media lists
7. Raw bilingual/admin fields not exposed in detail
8. Tags returned in detail response

### `PublicAlbumVideosAPITests` — 8 tests

1. Anonymous user can list videos for published album
2. Unpublished album returns 404
3. Missing album returns 404
4. Only public ready videos are returned
5. Private and non-ready videos are excluded
6. Response is paginated
7. `page_size` respected and capped
8. Response uses public video card shape; heavy/admin fields excluded

---

## Scalability Notes

- **Album list is paginated**: `PublicAlbumCursorPagination` — cursor-based,
  default 12, max 50. No unbounded response.

- **Album detail does not embed videos or media**: `PublicAlbumDetailSerializer`
  exposes album metadata only. Videos are only reachable via the separate
  `/videos/` endpoint.

- **Album videos are paginated separately**: `PublicAlbumVideosView` reuses
  `PublicVideoCursorPagination` from Phase 1 (default 12, max 50). Videos are
  never embedded in the album detail or list responses.

- **Populated filtering happens in the database**: `Exists` + `OuterRef` subqueries
  are evaluated by the database engine. No albums are loaded into Python memory
  and then discarded.

- **Serializers are thin**: `PublicAlbumCardSerializer` and
  `PublicAlbumDetailSerializer` expose only the fields required for public
  browsing. No raw bilingual fields, no admin-only fields, no full nested
  relations.

- **No Cloudflare calls during public browsing**: All three endpoints are
  read-only database queries. No Cloudflare Images or Cloudflare Stream APIs
  are called. Cover media URLs are already stored as `thumbnail_url` on
  `MediaItem`. Video playback/thumbnail URLs are already stored on `VideoClip`.

---

## Validation Results

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery --verbosity=1
# Ran 181 tests in 60.763s
# OK
```

- Previous test count: 151
- New tests added: 30
- Total: 181 tests, 0 failures, 0 errors

---

## What Was Not Changed

- `gallery/models.py` — not touched
- `gallery/migrations/` — no migrations created
- `gallery/urls.py` — not touched
- `gallery/admin.py` — not touched
- Legacy `/api/gallery/albums/` endpoints — not touched
- Admin endpoints — not touched
- Upload lifecycle — not modified
- Frontend files — not modified
- Caching — not added
- Search indexes — not added

---

## Next Recommended Step

**Phase 3B — Public image gallery media endpoint**

```
GET /api/public/albums/<slug>/media/
```

Cursor-paginated list of published `MediaItem` records for a published image
album, reusing or extending `MediaItemPublicSerializer`. This would complete
the symmetry between video albums (`/videos/`) and image albums (`/media/`).
