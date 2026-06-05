# Safe Public Caching Phase 7A Report

## Summary

Added `cache_page`-based TTL caching to two stable public read-only endpoints:
`GET /api/public/hero-video/` and `GET /api/public/albums/`. All changes are
confined to `gallery/views.py` and `gallery/tests.py`. No models, migrations,
serializers, URL patterns, settings, or frontend files were changed.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/views.py` | Added `method_decorator`, `cache_page` imports; added `_PUBLIC_CACHE_TTL = 60` constant; applied `@method_decorator(cache_page(_PUBLIC_CACHE_TTL), name='dispatch')` to `HeroVideoView` and `PublicAlbumListView` |
| `gallery/tests.py` | Added 7 smoke tests in `PublicCachedEndpointTests` |

---

## Endpoints Cached

### `GET /api/public/hero-video/`

```python
@method_decorator(cache_page(_PUBLIC_CACHE_TTL), name='dispatch')
class HeroVideoView(generics.GenericAPIView):
```

TTL: 60 seconds.

This endpoint fetches a single `VideoClip` record (the most recent
`is_public=True, status='ready'` clip). It is the most stable public endpoint
in the API — its content changes only when a new hero video is published, which
is a rare, deliberate admin action.

### `GET /api/public/albums/`

```python
@method_decorator(cache_page(_PUBLIC_CACHE_TTL), name='dispatch')
class PublicAlbumListView(LangContextMixin, generics.ListAPIView):
```

TTL: 60 seconds per unique URL.

This endpoint returns a cursor-paginated list of published albums. The
`?populated=true` variant runs two `Exists` subqueries per request, which
benefits most from caching. Because `cache_page` keys on the full URL
(including all query parameters and cursor values), each unique combination of
parameters is cached independently. Varying `?type=`, `?tag=`, `?search=`,
`?populated=`, `?page_size=`, and cursor values each produce separate cache
entries.

---

## Endpoints NOT Cached

No other endpoints were modified. Explicitly excluded:

| Endpoint pattern | Reason excluded |
|---|---|
| `POST/PATCH/DELETE` methods | Mutating requests must not be cached |
| `/api/gallery/admin/` | Admin/staff data; must always be fresh |
| `/api/public/messages/` | Visitor submissions; write-only |
| `/api/public/videos/<pk>/comments/` | User-submitted, recent data |
| `/api/gallery/admin/videos/*/refresh-status/` | Status-sync; must always hit Cloudflare |
| `/api/gallery/admin/*/direct-upload/` | Upload initiation; must never be cached |
| `/api/public/videos/` | Cursor pagination with frequently changing content |
| `/api/public/albums/<slug>/` | Album detail; rarely fetched in high volume |
| `/api/public/albums/<slug>/media/` | Media lists; dynamic per-album |
| `/api/public/albums/<slug>/videos/` | Video lists; dynamic per-album |

---

## Cache Implementation

```python
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

_PUBLIC_CACHE_TTL = 60  # seconds
```

`cache_page` is applied to the `dispatch` method via `method_decorator`. At TTL
expiry Django's cache backend removes the entry and the next request regenerates
it from the database.

No changes to `settings.py` or `CACHES` were made. Django's built-in default
cache backend (`django.core.cache.backends.locmem.LocMemCache`) is used without
explicit configuration, which is sufficient for single-process deployments.

---

## Cache Key Behaviour

`cache_page` constructs the cache key from:

1. The full request URL (path + query string)
2. Any `Vary` headers present in the first response for that URL

DRF adds `Vary: Accept` to all API responses (content negotiation). All API
clients sending `Accept: application/json` or `Accept: */*` map to the same
`Accept` value and share the same cache entry.

`corsheaders` middleware adds `Vary: Origin` at the middleware level, after the
view cache. Because `LocMemCache` serialises responses via `pickle`, each cache
retrieval returns a new Python object; `CorsMiddleware.process_response` applies
the correct `Access-Control-Allow-Origin` header to this fresh object on every
request. Cached data is never contaminated by a previous request's CORS headers.

---

## Invalidation Limitations

- **No active invalidation.** Cache entries expire after 60 seconds. If an admin
  publishes a new hero video or album, the public response will lag by up to 60s.
- **Per-process cache.** `LocMemCache` is not shared across Heroku dynos. With
  multiple dynos each process maintains its own cache. This is correct (no stale
  cross-request data) but reduces cache hit rates.
- **Multi-dyno production recommendation.** If the project is scaled to multiple
  Heroku dynos and cache effectiveness becomes important, switch to
  `django-redis` + a Redis add-on by setting `CACHES` in the environment. The
  `cache_page` decorator requires no code changes when `CACHES` is overridden.

---

## Tests Added

### `PublicCachedEndpointTests` — 7 smoke tests

Cache is cleared in `setUp` and `tearDown` to prevent cross-test interference.

1. Hero video returns 200 with the correct `cloudflare_uid`
2. Hero video returns 404 when no public ready video exists
3. Two consecutive requests to hero video return identical data
4. Public albums list returns only published albums
5. `?populated=true` filter returns the correct populated/empty subset

---

## Validation

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery --verbosity=1
# Ran 261 tests in 110.073s
# OK
```

- Previous test count: 253
- New tests added: 8
- Total: 261 tests, 0 failures, 0 errors

---

## What Was Not Changed

- `gallery/models.py` — not touched
- `gallery/migrations/` — no migrations created
- `gallery/serializers.py` — not touched
- `gallery/urls.py` — not touched
- `gallery/public_urls.py` — not touched
- `config/settings.py` — not touched (no CACHES configuration added)
- Admin endpoints — not changed
- Upload lifecycle — not modified
- Frontend files — not modified
