# Backend: Share Page Human Redirect + Autoplay

**Date:** 2026-06-07  
**Scope:** `gallery/share_helpers.py`, `gallery/share_views.py`  
**Status:** Implemented — `manage.py check` passing (0 issues)

---

## Files Changed

| File | Change type |
|---|---|
| `gallery/share_helpers.py` | Added `_CRAWLER_UA_FRAGMENTS` constant and `is_social_crawler()` function |
| `gallery/share_views.py` | Added `urllib.parse` imports, `HttpResponseRedirect` import, `is_social_crawler` import, `_build_redirect_url()` helper; added human redirect logic to all three share views |

No frontend files were touched. No migrations are needed. No models were changed. No serializers were changed.

---

## Crawler Detection Logic

Added to `gallery/share_helpers.py`:

```python
_CRAWLER_UA_FRAGMENTS = (
    "facebookexternalhit",
    "facebot",
    "meta-externalagent",
    "twitterbot",
    "linkedinbot",
    "slackbot",
    "discordbot",
    "whatsapp",
    "telegrambot",
)

def is_social_crawler(request) -> bool:
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(fragment in ua for fragment in _CRAWLER_UA_FRAGMENTS)
```

- Case-insensitive substring match against `HTTP_USER_AGENT`.
- Returns `True` → view serves OG HTML (crawler path).
- Returns `False` → view returns HTTP redirect (human browser path).
- No external dependencies. No DB queries.

---

## Redirect URL Helper

Added to `gallery/share_views.py`:

```python
def _build_redirect_url(frontend_url: str, extra_params: dict) -> str:
    parsed = urlparse(frontend_url)
    existing = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in extra_params.items():
        if key not in existing:
            existing[key] = [value]
    new_query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
```

- Uses `urllib.parse` only — no third-party packages.
- Preserves any query params already present in `frontend_url`.
- Does not duplicate a param that already exists.

---

## Human Redirect Behaviour

Privacy and 404 guards are evaluated **before** the crawler check. If the content is private, unpublished, or not found, the view raises `Http404` for both crawlers and humans. The redirect only fires for valid, public content.

### Video share (`/share/videos/<pk>/`)

Human browser receives:

```
HTTP 302 → https://kataphotos.com/videos/{pk}?utm_source=facebook&utm_medium=social&autoplay=1
```

Crawler receives: HTTP 200 OG HTML page (unchanged).

### Album share (`/share/albums/<slug>/`)

Human browser receives:

```
HTTP 302 → https://kataphotos.com/albums/{slug}?utm_source=facebook&utm_medium=social
```

Crawler receives: HTTP 200 OG HTML page (unchanged).

### Image share (`/share/images/<pk>/`)

Human browser receives:

```
HTTP 302 → https://kataphotos.com/images/{pk}?utm_source=facebook&utm_medium=social
```

Crawler receives: HTTP 200 OG HTML page (unchanged).

---

## Video Autoplay URL Behaviour

The `autoplay=1` param is appended only for video share redirects. Albums and images do not receive `autoplay`. The frontend is responsible for reading `autoplay=1` from the query string and auto-starting video playback.

The `autoplay` param is only added if not already present in `frontend_url` (enforced by `_build_redirect_url`).

---

## 404 Privacy Behaviour

The privacy guard runs before the crawler/human branch in all three views:

```python
try:
    video = VideoClip.objects.get(pk=pk, is_public=True, status=VideoClip.STATUS_READY)
except VideoClip.DoesNotExist:
    raise Http404("Video not found or not public.")
```

A private, unpublished, processing, failed, or missing resource returns **404** to both humans and crawlers. No content is leaked via the redirect.

---

## Manual Verification Steps

1. **Normal browser — video:**
   Open `http://localhost:8000/share/videos/1/` in a browser.  
   Expected: immediate redirect to `https://kataphotos.com/videos/1?utm_source=facebook&utm_medium=social&autoplay=1`.

2. **Facebook crawler — video:**
   ```
   curl -A "facebookexternalhit/1.1" http://localhost:8000/share/videos/1/
   ```
   Expected: HTTP 200, full HTML body with `<meta property="og:title">` etc. No `Location` header.

3. **Private/unready video:**
   Request any video with `is_public=False` or `status != 'ready'`.  
   Expected: HTTP 404 for both browser and crawler.

4. **Album — normal browser:**
   Open `http://localhost:8000/share/albums/divlje-ptice/`.  
   Expected: redirect to `https://kataphotos.com/albums/divlje-ptice?utm_source=facebook&utm_medium=social`.

5. **Image — normal browser:**
   Open `http://localhost:8000/share/images/12/`.  
   Expected: redirect to `https://kataphotos.com/images/12?utm_source=facebook&utm_medium=social`.

6. **Unpublished album/image:**
   Expected: HTTP 404.

---

## `manage.py check` Result

```
System check identified no issues (0 silenced).
```

---

## No Frontend Files Changed

This implementation is backend-only. The frontend receives the redirect and is responsible for consuming `autoplay=1` from the query string.

---

## Known Limitations (from share audit)

The `frontend_url` for videos currently resolves to `https://kataphotos.com/videos/{pk}` which still 404s on the frontend (see `documents/backend-docs/custom-analytics-and-share-audit.md` — Phase 0). The redirect now delivers humans to the correct path from the backend's perspective; the frontend route must be created separately.
