# Backend Public Gallery Type Contract Tightening

**Date:** 2026-06-06  
**Scope:** Public album list, album media, and album videos endpoints  
**Status:** Implemented and passing

---

## Summary

Three view-layer inconsistencies identified in the audit were fixed before the frontend photo/video gallery split. No models, serializers, URL routes, or admin endpoints were changed.

---

## Files Changed

| File | Change type |
|---|---|
| `gallery/views.py` | 4 changes (1 import, 3 view logic fixes) |
| `gallery/tests.py` | 5 new tests added across 3 existing test classes |

---

## Root Inconsistencies Fixed

### 1. Invalid `?type=` silently returned all albums

**Before:** The `if gallery_type in (...)` guard meant any value outside `'image'` / `'video'` was ignored and the full unfiltered album list was returned.

**After:** If `?type=` is present but not `'image'` or `'video'`, the view raises DRF `ValidationError` → HTTP 400.

```python
# gallery/views.py — PublicAlbumListView.get_queryset()
gallery_type = self.request.query_params.get('type')
if gallery_type is not None:
    if gallery_type not in (Album.GALLERY_TYPE_IMAGE, Album.GALLERY_TYPE_VIDEO):
        raise ValidationError(
            {"detail": "Invalid album type. Expected 'image' or 'video'."}
        )
    qs = qs.filter(gallery_type=gallery_type)
```

### 2. `/albums/<slug>/videos/` did not enforce `gallery_type == 'video'`

**Before:** `get_object_or_404(Album, slug=..., is_published=True)` — accepted any published album regardless of type.

**After:** `get_object_or_404(Album, slug=..., is_published=True, gallery_type=Album.GALLERY_TYPE_VIDEO)` — returns 404 for image albums.

### 3. `/albums/<slug>/media/` did not enforce `gallery_type == 'image'`

**Before:** Same as above — accepted any published album.

**After:** `get_object_or_404(Album, slug=..., is_published=True, gallery_type=Album.GALLERY_TYPE_IMAGE)` — returns 404 for video albums.

### 4. Import addition

`ValidationError` added to the existing DRF exceptions import line:

```python
from rest_framework.exceptions import APIException, ValidationError
```

---

## Final Behaviour Contract

### Valid `?type=` behaviour

| Request | Response |
|---|---|
| `GET /api/public/albums/` | 200 — all published albums |
| `GET /api/public/albums/?type=image` | 200 — image albums only |
| `GET /api/public/albums/?type=video` | 200 — video albums only |

### Invalid `?type=` behaviour

| Request | Response |
|---|---|
| `GET /api/public/albums/?type=photo` | 400 `{"detail": "Invalid album type. Expected 'image' or 'video'."}` |
| `GET /api/public/albums/?type=videos` | 400 |
| `GET /api/public/albums/?type=` | 400 (empty string is not `None` in Django query params) |
| `GET /api/public/albums/?type=all` | 400 |

### `/albums/<slug>/media/` wrong-type behaviour

| Album type | Response |
|---|---|
| `gallery_type='image'` and published | 200 — paginated image media |
| `gallery_type='video'` and published | 404 |
| Not published | 404 |
| Does not exist | 404 |

### `/albums/<slug>/videos/` wrong-type behaviour

| Album type | Response |
|---|---|
| `gallery_type='video'` and published | 200 — paginated public-ready videos |
| `gallery_type='image'` and published | 404 |
| Not published | 404 |
| Does not exist | 404 |

---

## Tests Added

### `PublicAlbumListAPITests` — 4 new tests

| Test method | What it verifies |
|---|---|
| `test_invalid_type_photo_returns_400` | `?type=photo` → HTTP 400 |
| `test_invalid_type_videos_returns_400` | `?type=videos` → HTTP 400 |
| `test_empty_type_string_returns_400` | `?type=` → HTTP 400 |
| `test_missing_type_returns_all_published` | No `?type=` param → 200, both image and video albums returned |

### `PublicAlbumVideosAPITests` — 1 new test

| Test method | What it verifies |
|---|---|
| `test_image_album_returns_404_on_videos_endpoint` | Image album slug on `/videos/` → HTTP 404 |

### `PublicAlbumMediaAPITests` — 1 new test

| Test method | What it verifies |
|---|---|
| `test_video_album_returns_404_on_media_endpoint` | Video album slug on `/media/` → HTTP 404 |

---

## Commands Run

```
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test gallery --verbosity=1
```

## Test Results

```
System check identified no issues (0 silenced).

Ran 264 tests in 105.083s

OK
```

All 264 tests passed. The suite grew from 259 to 264 tests (5 new).

---

## What Was Intentionally Not Implemented

| Item | Reason |
|---|---|
| Model changes | Not needed; `gallery_type` field already exists on `Album` |
| Serializer field changes | `gallery_type` is already exposed in `PublicAlbumCardSerializer` and `PublicAlbumDetailSerializer` |
| Route renaming | Existing route names are correct and stable |
| Admin endpoint changes | Admin endpoints are unaffected and not part of the public contract |
| `GET /api/public/albums/<slug>/` type enforcement | The detail view serves any published album regardless of type — this is correct, as the frontend needs to read `gallery_type` from this response to decide which sub-endpoint (`/media/` or `/videos/`) to call |
| 400 vs 404 for wrong-type sub-endpoints | Project convention uses 404 for any wrong-resource-type access at the public level; `get_object_or_404` with the type filter produces this naturally |
| `?type=` validation on non-list endpoints | Only the list endpoint accepts `?type=`; sub-endpoints are type-enforced via the album lookup, not a query param |
