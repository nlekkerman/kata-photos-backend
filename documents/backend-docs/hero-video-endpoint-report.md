# Hero Video Endpoint Report

Date: 2026-06-04

## Summary

Added a single public endpoint that returns the most recently created, publicly available video for use in the landing-page hero section.

---

## Endpoint

```
GET /api/public/hero-video/
```

- **Permission**: `AllowAny` (no authentication required)
- **Response**: `200 OK` with hero video JSON, or `404 Not Found` if no qualifying video exists

---

## Filtering Logic

Returns the first result of:

```python
VideoClip.objects
    .filter(is_public=True, status=VideoClip.STATUS_READY)
    .order_by('-created_at')
    .first()
```

**Timestamp field used for "latest"**: `created_at` (`DateTimeField`, `auto_now_add=True`, defined on `VideoClip`).  
The `VideoClip.Meta` already uses `ordering = ['-created_at']`. The view applies `.order_by('-created_at')` explicitly for clarity.

---

## Response Fields

All fields are real model or related-model fields — no invented fields:

| Field | Source |
|---|---|
| `id` | `VideoClip.id` |
| `title_bs` | `VideoClip.title_bs` |
| `title_en` | `VideoClip.title_en` |
| `album_id` | `VideoClip.album_id` (FK) |
| `album_title_bs` | `VideoClip.album.title_bs` (via `select_related`) |
| `album_title_en` | `VideoClip.album.title_en` (via `select_related`) |
| `duration_seconds` | `VideoClip.duration_seconds` |
| `cloudflare_uid` | `VideoClip.cloudflare_uid` |
| `cloudflare_playback_url` | `VideoClip.cloudflare_playback_url` |
| `cloudflare_thumbnail_url` | `VideoClip.cloudflare_thumbnail_url` |

`album_title_bs` and `album_title_en` return `''` when `album` is `None`.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `HeroVideoSerializer` class at end of file |
| `gallery/views.py` | Added `HeroVideoSerializer` to imports; added `HeroVideoView` class at end of file |
| `gallery/public_urls.py` | **New file** — URL router for `api/public/` prefix |
| `config/urls.py` | Added `path("api/public/", include("gallery.public_urls"))` |

---

## Serializer Used

`HeroVideoSerializer` — new, defined in `gallery/serializers.py`.  
Uses `serializers.ModelSerializer` with two `SerializerMethodField` entries for album titles.

---

## Files Intentionally Not Touched

- `gallery/models.py` — no model changes needed; all required fields already exist on `VideoClip`
- `gallery/urls.py` — existing gallery URL patterns unchanged
- `gallery/admin.py` — not relevant
- `gallery/migrations/` — no schema changes
- `gallery/services/` — not relevant
- `auth_api/` — not relevant
- All image-related views and serializers
- All FieldNote views and serializers
- All admin-only views

---

## Validation Results

```
python manage.py check
→ System check identified no issues (0 silenced)

python manage.py test gallery.tests --verbosity=2
→ Ran 42 tests in 39.250s
→ OK
```
