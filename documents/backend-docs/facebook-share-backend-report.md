# Backend: Facebook / Social Share — Open Graph Foundation

**Date:** 2026-06-06
**Scope:** Public HTML share pages with Open Graph metadata + share fields in public serializers
**Status:** Implemented — `manage.py check` passing (0 issues)

---

## Files Changed

| File | Change type |
|---|---|
| `gallery/share_helpers.py` | **Created** — OG metadata builders and lightweight share-info helpers |
| `gallery/share_views.py` | **Created** — HTML-rendering Django views for the three share page types |
| `gallery/share_urls.py` | **Created** — URL patterns for the `/share/` prefix |
| `config/urls.py` | `path("share/", include("gallery.share_urls"))` added |
| `config/settings.py` | `FRONTEND_URL` and `FALLBACK_OG_IMAGE` settings added |
| `gallery/serializers.py` | `share_helpers` imported; 4 share fields added to 5 public serializers |

No frontend files were touched. No automated tests were run.

---

## Share Routes Added

| URL pattern | View | Name |
|---|---|---|
| `/share/albums/<slug>/` | `AlbumShareView` | `share-album` |
| `/share/videos/<pk>/` | `VideoShareView` | `share-video` |
| `/share/images/<pk>/` | `ImageShareView` | `share-image` |

All routes are mounted at the project root via `config/urls.py`.  They are entirely separate from the existing `/api/public/` and `/api/gallery/` routes.

---

## Share Page Behaviour

Each share page:

1. Looks up the content by slug/pk and validates it is **public/published**.
2. Returns **404** (not a redirect, not metadata) if the content is private, unpublished, or missing.
3. Returns a **full HTML response** (`text/html`) with correct Open Graph and Twitter card meta tags in `<head>`.
4. Renders a simple visible fallback `<body>` with a thumbnail, title, description, and a link to the real frontend page.
5. **Does NOT auto-redirect** — Facebook's crawler must be able to fetch and parse the page.

Privacy enforcement:

| Model | Guard condition |
|---|---|
| `Album` | `is_published=True` |
| `VideoClip` | `is_public=True` AND `status='ready'` |
| `MediaItem` | `is_published=True` AND `media_type='image'` |

---

## Open Graph Meta Tags Rendered

```html
<meta property="og:type" content="...">
<meta property="og:site_name" content="Kata Wild">
<meta property="og:title" content="...">
<meta property="og:description" content="...">
<meta property="og:image" content="...">
<meta property="og:url" content="...">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="...">
<meta name="twitter:description" content="...">
<meta name="twitter:image" content="...">
```

All values are HTML-escaped via `html.escape()` before insertion.

---

## Metadata Source Priority

### Albums
| Field | Priority |
|---|---|
| `og:title` | `title_bs` → `title_en` → `title` → `"Album {pk}"` |
| `og:description` | `description_bs` → `description_en` → `seo_description_bs` → `seo_description_en` → generic Bosnian fallback |
| `og:image` | `cover_media.thumbnail_url` → `cover_media.public_url` → first published image `thumbnail_url` → first public video `cloudflare_thumbnail_url` → `FALLBACK_OG_IMAGE` |

### Videos
| Field | Priority |
|---|---|
| `og:title` | `title_bs` → `title_en` → `"Video {pk}"` |
| `og:description` | `description_bs` → `description_en` → generic Bosnian fallback |
| `og:image` | `cloudflare_thumbnail_url` → album `cover_media.thumbnail_url` → `FALLBACK_OG_IMAGE` |
| `og:type` | `video.other` |

### Images / Media Items
| Field | Priority |
|---|---|
| `og:title` | `title_bs` → `title_en` → album `title_bs` → album `title_en` → `"Fotografija {pk}"` |
| `og:description` | `description_bs` → `description_en` → `caption_bs` → album `description_bs` → generic fallback |
| `og:image` | `thumbnail_url` → `public_url` → `FALLBACK_OG_IMAGE` |

---

## Frontend URLs

| Type | Frontend URL pattern |
|---|---|
| Album | `{FRONTEND_URL}/albums/{slug}` |
| Video | `{FRONTEND_URL}/videos/{pk}` |
| Image | `{FRONTEND_URL}/images/{pk}` |

`FRONTEND_URL` defaults to `https://kataphotos.com` and can be overridden via env var.

---

## Facebook Share URL Format

The frontend should open a Facebook sharer popup using:

```
https://www.facebook.com/sharer/sharer.php?u=<encoded-share-url>
```

Example:

```
https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fkata-wild-backend-5b989da54ce2.herokuapp.com%2Fshare%2Fvideos%2F42%2F
```

The `facebook_share_url` field in API responses is pre-computed and ready to use directly.

---

## New Settings Added (`config/settings.py`)

```python
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://kataphotos.com")
FALLBACK_OG_IMAGE = os.getenv("FALLBACK_OG_IMAGE", "")
```

`FALLBACK_OG_IMAGE` should be set to an absolute HTTPS URL of a static image (e.g. site logo or hero image hosted on the CDN) via Heroku config var. Leave empty to skip the fallback image tag.

---

## New Share Fields in Public Serializers

The following four fields were added to five public serializers:

| Field | Type | Notes |
|---|---|---|
| `share_url` | string | Absolute backend share page URL |
| `facebook_share_url` | string | Pre-built Facebook sharer URL |
| `frontend_url` | string | Human-readable frontend URL on kataphotos.com |
| `is_shareable` | boolean | `true` only if the item is currently public/published/ready |

### Serializers updated

| Serializer | Endpoint |
|---|---|
| `PublicVideoCardSerializer` | `GET /api/public/videos/` |
| `PublicVideoDetailSerializer` | `GET /api/public/videos/<pk>/` |
| `PublicAlbumCardSerializer` | `GET /api/public/albums/` |
| `PublicAlbumDetailSerializer` | `GET /api/public/albums/<slug>/` |
| `MediaItemPublicSerializer` | `GET /api/public/albums/<slug>/media/` |

No existing fields were modified or removed. Existing response shapes are fully preserved.

---

## No Facebook API or SDK Used

- No Facebook Graph API integration.
- No Facebook OAuth.
- No Meta/Facebook SDK.
- No direct posting to Facebook.
- Sharing uses only the free public sharer URL: `https://www.facebook.com/sharer/sharer.php?u=`.

---

## `manage.py check` Result

```
System check identified no issues (0 silenced).
```

---

## Manual Verification Steps

1. **Local: find or create a published album** (e.g. slug `divlje-ptice`).
2. Open `http://localhost:8000/share/albums/divlje-ptice/` in a browser.
3. View HTML source — confirm `og:title`, `og:description`, `og:image`, `og:url` are present and correct.
4. **Find or create a public ready video** (pk e.g. `3`).
5. Open `http://localhost:8000/share/videos/3/`.
6. Confirm `og:image` matches the Cloudflare Stream thumbnail URL.
7. **Find or create a published image media item** (pk e.g. `12`).
8. Open `http://localhost:8000/share/images/12/`.
9. Confirm OG image resolves to the media item's `thumbnail_url` or `public_url`.
10. Confirm private/unpublished items return **404** from the share URL.
11. **Paste production share URLs** into [Meta Sharing Debugger](https://developers.facebook.com/tools/debug/) to validate crawlable preview.
12. Confirm `GET /api/public/videos/<pk>/` response now includes `share_url`, `facebook_share_url`, `frontend_url`, `is_shareable` fields.
13. Confirm a video with `status != 'ready'` has `is_shareable: false`.

---

## Heroku Environment Variables (optional)

| Var | Recommended value |
|---|---|
| `FRONTEND_URL` | `https://kataphotos.com` (already the default) |
| `FALLBACK_OG_IMAGE` | Absolute URL to a static fallback image (e.g. `https://kataphotos.com/og-image.jpg`) |

Set via:
```
heroku config:set FRONTEND_URL=https://kataphotos.com --app kata-wild-backend
heroku config:set FALLBACK_OG_IMAGE=https://kataphotos.com/og-image.jpg --app kata-wild-backend
```

---

## What Was Intentionally Not Implemented

| Item | Reason |
|---|---|
| Facebook Graph API / OAuth | Not requested; free sharer URL is sufficient |
| Facebook SDK | Not needed for basic share popup |
| Automated tests | Explicitly excluded per task constraints |
| Share pages for FieldNotes | Not in task scope |
| Share pages for VideoTimestampComments | Not in task scope |
| Admin serializer share fields | Not requested; admin API already has all raw fields |
| `is_shareable` guard in the share view itself | View already returns 404 for non-public content; `is_shareable` in serializers serves the upload-flow UX |
| Auto-redirect to frontend | Explicitly prohibited — Facebook must scrape the page |
| Hero-video share page | Not in task scope; hero video is already handled by VideoShareView via `/share/videos/<pk>/` |
