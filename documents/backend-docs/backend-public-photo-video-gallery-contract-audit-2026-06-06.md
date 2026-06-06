# Backend Public Photo/Video Gallery Separation Contract Audit

**Date:** 2026-06-06  
**Scope:** Public album and video endpoints — gallery type separation contract  
**Status:** Audit only — no code was changed

---

## Executive Summary

The backend contract is already clean and sufficient to support a frontend split into `/gallery` (photo/image albums) and `/videos` (video albums) pages using existing endpoints. The `gallery_type` field is stored on the `Album` model, exposed in all public serializers, and the public album list endpoint supports `?type=image` / `?type=video` filtering backed by tests.

**Conclusion: A — Backend contract is already clean; frontend can split using existing endpoints.**

One minor behavioural gap (invalid `?type` value silently returns all albums instead of an empty list or an error) is noted below and should be considered before relying on URL-based type routing in the frontend.

---

## Endpoint Contract Table

| Endpoint | Purpose | Supports image? | Supports video? | Pagination | Notes |
|---|---|---|---|---|---|
| `GET /api/public/albums/` | List all published albums | Yes | Yes | Cursor (page_size=12, max=50) | Supports `?type=`, `?tag=`, `?search=`, `?populated=`, `?lang=` |
| `GET /api/public/albums/?type=image` | List image/photo albums only | Yes | No | Cursor (page_size=12, max=50) | Backed by test #9 |
| `GET /api/public/albums/?type=video` | List video albums only | No | Yes | Cursor (page_size=12, max=50) | Backed by test #8 |
| `GET /api/public/albums/<slug>/` | Single published album detail | Yes | Yes | N/A (single object) | Returns `gallery_type` field; no type enforcement at this level |
| `GET /api/public/albums/<slug>/media/` | Paginated published image media for album | Yes (`media_type='image'`) | No | Cursor (page_size=12, max=50) | 404 if album missing or unpublished; does not enforce `album.gallery_type` |
| `GET /api/public/albums/<slug>/videos/` | Paginated public-ready videos for album | No | Yes (`is_public=True`, `status='ready'`) | Cursor (default page_size from `PublicVideoCursorPagination`) | 404 if album missing or unpublished; does not enforce `album.gallery_type` |
| `GET /api/public/videos/` | Independent cross-album video browse | No | Yes | Cursor | Supports `?album=`, `?tag=`, `?search=`, `?lang=`; album-independent |
| `GET /api/public/videos/<pk>/` | Single public-ready video detail | No | Yes | N/A (single object) | 404 for private, uploading, processing, or failed |

---

## Filter and Query Parameter Table

| Query/filter | Endpoint | Values | Validation behaviour | Tested? |
|---|---|---|---|---|
| `?type=` | `GET /api/public/albums/` | `image`, `video` | **Silent passthrough on invalid value** — unknown value is ignored, all published albums returned | Yes (valid values only) |
| `?tag=<slug>` | `GET /api/public/albums/` | Any tag slug | Unknown slug → empty result (no error) | Yes |
| `?search=<query>` | `GET /api/public/albums/` | Free text | icontains across `title_bs`, `title_en`, `description_bs`, `description_en` | Yes |
| `?populated=true` | `GET /api/public/albums/` | `true` | Excludes albums with no published images (image type) or no public-ready videos (video type). Combines correctly with `?type=` | Yes |
| `?lang=en\|bs` | All public endpoints | `en`, `bs` | Unknown value falls back to `en` | Yes (bs, defaults) |
| `?page_size=<n>` | All paginated public endpoints | Integer | Capped at per-endpoint maximum (50 for albums, 100 for comments) | Yes |
| `?album=<pk>` | `GET /api/public/videos/` | Integer PK | Unknown PK → empty result (no error) | Yes |
| `?tag=<slug>` | `GET /api/public/videos/` | Any tag slug | Unknown slug → empty result (no error) | Yes |
| `?search=<query>` | `GET /api/public/videos/` | Free text | icontains across title and description fields | Yes |

---

## Answers to Audit Questions

### 1. Does the public album list endpoint support filtering by gallery type?

**Yes.** `PublicAlbumListView.get_queryset()` reads `self.request.query_params.get('type')` and applies `qs.filter(gallery_type=gallery_type)` when the value is `'image'` or `'video'`.

Source: `gallery/views.py`, `PublicAlbumListView.get_queryset()` lines ~1288–1297.

### 2. What is the exact query parameter name?

**`type`**

Example: `GET /api/public/albums/?type=image`

### 3. What values are supported?

**`image`** and **`video`**, matching `Album.GALLERY_TYPE_IMAGE` and `Album.GALLERY_TYPE_VIDEO` constants defined in `gallery/models.py`.

### 4. Does the serializer expose `gallery_type`?

**Yes.** Both public album serializers include `gallery_type` in their `fields` lists:

- `PublicAlbumCardSerializer.Meta.fields`: `[..., 'gallery_type', ...]`
- `PublicAlbumDetailSerializer.Meta.fields`: `[..., 'gallery_type', ...]`

Source: `gallery/serializers.py`, lines 1196 and 1222.

### 5. Are image albums and video albums represented by the same model or separate models?

**Same model: `Album`.** A single `gallery_type` CharField (`'image'` or `'video'`) distinguishes the type. However, their *content* lives in two separate models:

- Image content → `MediaItem` (linked via `album` FK, `media_type='image'`)
- Video content → `VideoClip` (linked via `album` FK, Cloudflare Stream managed)

This is a one-container / two-content-model architecture. The admin API also enforces this separation via dedicated gallery endpoints (`/api/gallery/admin/image-galleries/` and `/api/gallery/admin/video-galleries/`).

### 6. Does `GET /api/public/albums/?type=image` return only image/photo albums?

**Yes.** Confirmed by test `PublicAlbumListAPITests.test_type_image_filter` (test #9 in the test class). The queryset is filtered to `gallery_type='image'` and the test asserts that only the image album slug is present while the video album slug is absent.

### 7. Does `GET /api/public/albums/?type=video` return only video albums?

**Yes.** Confirmed by test `PublicAlbumListAPITests.test_type_video_filter` (test #8). Same pattern as above.

### 8. What happens for invalid `type` values?

**Silent passthrough — all published albums are returned.** The view code is:

```python
gallery_type = self.request.query_params.get('type')
if gallery_type in (Album.GALLERY_TYPE_IMAGE, Album.GALLERY_TYPE_VIDEO):
    qs = qs.filter(gallery_type=gallery_type)
```

If `gallery_type` is anything other than `'image'` or `'video'` (e.g. `'photo'`, `'all'`, `''`, `None`), the `if` condition is false and the filter is not applied. The endpoint returns all published albums of both types. **No test covers this edge case.**

This means a frontend typo like `?type=photo` would silently return all albums rather than an empty list — a potential source of confusion. No error is surfaced.

### 9. Are these filters tested?

**Yes — for valid values.** Tests #8 and #9 in `PublicAlbumListAPITests` (`gallery/tests.py` lines 1654–1672) cover `?type=video` and `?type=image`. Combined filters (`?populated=true&type=video` and `?populated=true&type=image`) are also tested (tests #13 and #14).

**Not tested:** invalid/unknown `?type` value behaviour.

### 10. Are video album detail pages supported through `GET /api/public/albums/<slug>/videos/`?

**Yes.** `PublicAlbumVideosView` is a cursor-paginated `ListAPIView` that:
- Resolves the album by slug (404 if not found or unpublished)
- Returns all `VideoClip` objects where `album=<album>`, `is_public=True`, `status='ready'`
- Uses `PublicVideoCardSerializer`
- Allows anonymous access

Note: the view does **not** enforce that the album's `gallery_type` is `'video'`. A request to `/api/public/albums/<image-album-slug>/videos/` would succeed (returning an empty list if the image album has no VideoClip records) rather than returning 404.

### 11. Are image album detail pages supported through `GET /api/public/albums/<slug>/media/`?

**Yes.** `PublicAlbumMediaView` is a cursor-paginated `ListAPIView` that:
- Resolves the album by slug (404 if not found or unpublished)
- Returns all `MediaItem` objects where `album=<album>`, `is_published=True`, `media_type='image'`
- Uses `MediaItemPublicSerializer`
- Allows anonymous access

Same note: the view does **not** enforce `album.gallery_type == 'image'`.

### 12. Is `/api/public/videos/` intended for individual video browsing/search, independent of video albums?

**Yes.** `PublicVideoListView` is a standalone cursor-paginated list of all public-ready `VideoClip` records across all albums. It is:
- Not scoped to a single album (album is an optional filter, not required)
- Searchable via `?search=`, filterable by `?album=` PK and `?tag=`
- Intended as the global video browse surface (analogous to a `/videos` page)
- Distinct from `/api/public/albums/<slug>/videos/` which is scoped to one album

### 13. Are public album endpoints paginated for both image and video album types?

**Yes, all paginated using cursor pagination:**

| View | Paginator class | Default page_size | Max page_size |
|---|---|---|---|
| `PublicAlbumListView` | `PublicAlbumCursorPagination` | 12 | 50 |
| `PublicAlbumVideosView` | `PublicVideoCursorPagination` | (set in class) | 100 |
| `PublicAlbumMediaView` | `PublicAlbumMediaCursorPagination` | 12 | 50 |
| `PublicVideoListView` | `PublicVideoCursorPagination` | (set in class) | 100 |

Pagination applies equally regardless of `gallery_type`. The `?type=` filter interacts correctly with cursor pagination (cursors are type-stable for a given filtered URL).

### 14. Is there any legacy `/api/gallery/*` behavior that frontend should avoid for public pages?

**Yes — two legacy routes exist under `/api/gallery/` that should not be used for public-facing pages:**

1. **`GET /api/gallery/albums/`** (`AlbumListCreateView`) — Lists all published albums. Key differences from the canonical public endpoint:
   - Does **not** support `?type=` filtering by gallery type
   - Does **not** support `?populated=` filtering
   - Does **not** use cursor pagination (no pagination class applied)
   - Is also a `POST` endpoint for admin album creation
   - Frontend should use `/api/public/albums/` instead

2. **`GET /api/gallery/videos/`** (`VideoClipListView`) — Lists VideoClip objects with mixed admin/public visibility logic (staff see all; public sees `is_public=True` + `status='ready'`). Key differences:
   - No cursor pagination (no pagination class applied)
   - `?album=` filter uses PK (not slug)
   - Mixed permission model (public but admin-augmented behaviour)
   - Frontend should use `/api/public/videos/` instead

---

## Observed Gaps (Not Blockers)

These are minor issues that do not prevent the frontend split, but are worth noting:

| Gap | Impact | Severity |
|---|---|---|
| Invalid `?type=` value silently returns all albums (no validation or 400 error) | Frontend typo in type value would appear to work but return wrong data | Low |
| `PublicAlbumVideosView` does not enforce `album.gallery_type == 'video'` | Requesting videos for an image album returns an empty list instead of 404 | Low |
| `PublicAlbumMediaView` does not enforce `album.gallery_type == 'image'` | Requesting media for a video album returns an empty list instead of 404 | Low |
| No test for invalid `?type=` passthrough behaviour | Edge case undocumented by tests | Low |
| `PublicVideoCursorPagination` page_size not visible from this audit (not defined inline in view) | Not a functional gap — just documentation completeness | Informational |

None of these gaps require backend changes before the frontend split can proceed safely.

---

## Conclusion

**A — Backend contract is already clean; frontend can split using existing endpoints.**

The backend provides:
- A unified `Album` model with `gallery_type` field (`'image'` | `'video'`)
- A tested `?type=` filter on `GET /api/public/albums/`
- `gallery_type` exposed in both the list (`PublicAlbumCardSerializer`) and detail (`PublicAlbumDetailSerializer`) responses
- Separate sub-endpoints for album content: `…/media/` for images, `…/videos/` for video clips
- A standalone cross-album video browse endpoint at `GET /api/public/videos/`
- Cursor pagination on all public endpoints
- Tests confirming both `type=image` and `type=video` filter correctly

The frontend can safely implement:

```
/gallery  → GET /api/public/albums/?type=image
/videos   → GET /api/public/albums/?type=video
             (plus /api/public/videos/ for the standalone video search page)
```

No backend changes are required before the frontend split.
