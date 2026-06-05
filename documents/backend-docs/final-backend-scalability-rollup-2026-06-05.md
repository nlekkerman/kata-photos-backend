# Final Backend Scalability Rollup

## Summary

All backend scalability, cleanup, and operations hardening phases are complete.
The backend is paginated end-to-end, has structured error logging on all provider
paths, caches two stable public endpoints, and has a documented cleanup and
search-index strategy ready for when data volume justifies it.

Starting test count (before any phase in this roadmap): 229
Final test count: 258
Net tests added across roadmap: 29
All 258 tests pass. Zero failures. Zero errors.

---

## Completed Phases

| Phase | Description | Files Changed | Tests Added |
|---|---|---|---|
| 1 | Public video cursor pagination | views.py, public_urls.py | — |
| 2A | Public VideoClip indexes | models.py, migration | — |
| 2B | Queryset optimization cleanup | views.py | — |
| 3A | Public album endpoints | views.py, public_urls.py | — |
| 3B | Public album media endpoint | views.py, public_urls.py | — |
| 3C | Frontend switch to /api/public/* | frontend | — |
| 4A | Admin video pagination + filters | views.py, tests.py | 20 |
| 4B | Frontend admin video pagination | frontend | — |
| 4C | Admin image/media pagination + filters | views.py, tests.py | 17 |
| 4D | Frontend admin image pagination | frontend | — |
| 5A | Upload lifecycle safety | serializers.py, views.py, tests.py | ~13 |
| 5B | Frontend upload lifecycle UI | frontend | — |
| **6A** | **Public comment cursor pagination** | views.py, tests.py | **11** |
| **7A** | **Safe public caching** | views.py, tests.py | **8** |
| **8A** | **Search scalability audit** | documents/ only | — |
| **9A** | **Provider cleanup/archive audit** | documents/ only | — |
| **10A** | **Monitoring/observability basics** | cloudflare_images.py, views.py | — |

---

## Public Browsing Scalability

All public read endpoints are paginated and bounded:

| Endpoint | Pagination | Default | Max |
|---|---|---|---|
| `GET /api/public/videos/` | Cursor | 12 | 50 |
| `GET /api/public/albums/` | Cursor | 12 | 50 |
| `GET /api/public/albums/<slug>/videos/` | Cursor | 12 | 50 |
| `GET /api/public/albums/<slug>/media/` | Cursor | 12 | 50 |
| `GET /api/public/videos/<pk>/comments/` | Cursor | 20 | 100 |

Cursor pagination is used throughout public browsing. No public list endpoint
returns an unbounded response.

Public browsing queries use `select_related` and `prefetch_related` where
appropriate. No N+1 queries exist on the critical read paths.

---

## Admin Scalability

All admin list endpoints are paginated and filterable:

| Endpoint | Pagination | Default | Max | Filters |
|---|---|---|---|---|
| `GET /api/gallery/admin/videos/` | Page-number | 50 | 100 | album, status, is_published, search |
| `GET /api/gallery/admin/images/` | Page-number | 50 | 100 | album, is_published, provider, search |

Admin queries use `select_related('album')` and all filters execute at the
database level — no Python-level post-filter.

---

## Upload Lifecycle Safety

VideoClip upload lifecycle enforces:

1. New direct uploads always start `status='uploading'`, `is_public=False`
2. `complete-upload` advances status to `processing` only
3. `refresh-status` syncs from Cloudflare — only sets `ready` or `failed`
4. Failed videos are forced `is_public=False` on status sync
5. Admin cannot set `is_published=True` while `status != 'ready'`
6. Image uploads enforce 10 MB max size and JPEG/PNG/WebP content-type only

---

## Comments Pagination

`GET /api/public/videos/<pk>/comments/` is now cursor-paginated:

- Default page size: 20
- Max page size: 100
- Ordering: `timestamp_seconds`, `id` (matches `VideoTimestampComment.Meta.ordering`)
- Only `status='approved'` comments are returned
- `author_email` is never exposed in any response
- POST (submit comment) behaviour unchanged; new comments arrive as `status='pending'`

**Frontend must read `response.data.results`.** The response shape changed from
a raw array to a cursor-paginated object in this phase.

---

## Caching

Two stable public read-only endpoints are cached for 60 seconds per unique URL:

| Endpoint | TTL | Cache key basis |
|---|---|---|
| `GET /api/public/hero-video/` | 60s | full URL |
| `GET /api/public/albums/` | 60s | full URL + query string |

Implementation: Django `cache_page` via `method_decorator`. Default
`LocMemCache` backend — per-process, no shared state between Heroku dynos.

**Not cached:** admin endpoints, upload endpoints, status-sync endpoints,
visitor messages, comment submission, video detail, album detail, album media.

**Multi-dyno note:** For production with multiple dynos, switch to a shared
Redis cache backend (`django-redis` + Heroku Redis add-on). The `cache_page`
decorator requires no code change when `CACHES` is overridden in environment
configuration.

---

## Search

**No `pg_trgm` indexes were added. The audit concluded they are not justified at current scale.**

Current `icontains` search coverage:

| Endpoint | Fields searched | Join risk |
|---|---|---|
| Public video list | 4 title/description fields | None |
| Public album list | 4 title/description fields | None |
| Admin video list | 11 fields including tags | M2M tags fan-out |
| Admin image list | 13 fields including album | FK join only (safe) |
| Legacy album list | 7 fields including tags | M2M tags fan-out |

Recommended future trigger for `pg_trgm`: VideoClip row count exceeds ~50,000
and measurable latency is observed on `/api/public/videos/?search=`. First
indexes to add when justified: `VideoClip.title_bs`, `VideoClip.title_en`,
`Album.title_bs`, `Album.title_en`.

---

## Provider Cleanup / Archive

**No code changes were made.** The audit documented the current state:

- `DELETE` on VideoClip removes only the Django record; Cloudflare Stream asset
  is NOT deleted (documented in the view docstring).
- `DELETE` on MediaItem removes only the Django record; local files and
  Cloudflare Images assets are NOT deleted.
- `status='uploading'` records accumulate if upload is never completed.
- `status='failed'` records accumulate with no automatic expiry.
- No soft-archive field exists on `VideoClip` or `MediaItem`.

Recommended next steps (not implemented — require separate focused phases):

1. Management command to list orphan upload candidates (read-only, safe)
2. Management command to clean stale-uploading records with `--dry-run` / `--confirm`
3. `perform_destroy` override for local file deletion on MediaItem delete
4. Cloudflare Stream asset deletion on VideoClip delete (requires new service function + tests)
5. Cloudflare Images asset deletion on MediaItem delete (same pattern)

---

## Observability

Structured `logger.error()` calls now cover all provider failure paths:

| Failure path | Service layer | View layer |
|---|---|---|
| Cloudflare Stream direct upload | Yes | Yes |
| Cloudflare Stream sync/refresh | Yes | Yes |
| Cloudflare Images upload — HTTP error | **Added 10A** | **Added 10A** |
| Cloudflare Images upload — network error | **Added 10A** | **Added 10A** |
| Cloudflare Images upload — API non-success | **Added 10A** | **Added 10A** |
| Email reply failure | n/a | Yes |

Log format uses `%s` / `%r` interpolation (not f-strings) so the Python logging
framework can suppress format cost for below-threshold levels. API tokens are
never included in log messages.

No external monitoring SDK (Sentry etc.) was added. The standard Python
`logging` approach is a safe, zero-dependency first step. Adding `sentry-sdk`
later requires only a `settings.py` change and no view/service modifications.

---

## Remaining Risks

| Risk | Priority | Status |
|---|---|---|
| Cloudflare Stream assets not deleted on VideoClip DELETE | High (as volume grows) | Documented, not implemented |
| Cloudflare Images assets not deleted on MediaItem DELETE | High (as volume grows) | Documented, not implemented |
| Local `original_file` not deleted on MediaItem DELETE | Medium | Documented, not implemented |
| Stale `status='uploading'` records accumulate | Medium | Documented, not implemented |
| `pg_trgm` not present; `icontains` search degrades above ~50k rows | Low (current scale) | Documented; trigger defined |
| LocMemCache not shared across Heroku dynos | Low (current dyno count) | Documented; Redis path defined |
| No Sentry / external error monitoring | Low | Documented; integration path defined |
| `VideoClip.tags` M2M join in admin search may produce large intermediary | Low (admin only) | Documented in 8A |

---

## Recommended Production Deployment Order

1. **Phase 6A** (comment pagination) — breaking change to public comments response shape.
   Deploy after confirming frontend reads `response.data.results` for comments.

2. **Phase 7A** (caching) — safe, additive. Deploy any time.

3. **Phase 10A** (logging) — safe, additive. Deploy any time.

4. **Phase 8A / 9A** — audit-only; nothing to deploy.

---

## Validation Summary

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery --verbosity=1
# Ran 258 tests in ~105s
# OK
# 0 failures, 0 errors
```

| Phase | Tests before | Tests after | Added |
|---|---|---|---|
| 4C (baseline for this roadmap) | 212 | 229 | 17 |
| 5A upload lifecycle | 229 | 242 | 13 |
| 6A comment pagination | 242 | 253 | 11 |
| 7A public caching | 253 | 258 | 5 + cache isolation fix |
| 8A–10A | 258 | 258 | 0 (audit + logging only) |
| **Final** | — | **258** | — |
