# Gallery and Media Architecture Plan

## Current Repository State

- **Django 6.0.5**, **DRF 3.17.1**, **python-dotenv 1.2.2** — no other packages installed
- `gallery/models.py`, `gallery/views.py`, `gallery/admin.py` are blank boilerplate
- `config/urls.py` contains only Django admin — no API routes defined
- `config/settings.py` has `MEDIA_ROOT` and `MEDIA_URL` configured for local storage; `DEFAULT_AUTO_FIELD` not yet set explicitly
- SQLite database (`db.sqlite3`) — no gallery migrations exist yet
- `documents/` folder exists
- No Cloudinary, Cloudflare R2, Cloudflare Stream, or any cloud storage packages present
- `gallery/apps.py` uses `name = 'gallery'` without explicit `default_auto_field`

---

## Architecture Goals

1. Backend is the single canonical source of truth for all media state and URLs
2. Frontend consumes only normalized, ready-to-render URLs — never constructs them
3. Model design is provider-agnostic from day one — swapping Cloudinary or Cloudflare Stream later does not break the API contract
4. Public API exposes only published content; admin API exposes full management surface
5. MVP ships image support; video model fields are stubbed but video upload is deferred
6. URL structure is stable enough that slug/ID-based frontend routes never need to change

---

## Non-Negotiable Rules

- No fake backend simulation in frontend
- No fake auth or upload
- No fallback mock gallery data
- If frontend needs real data, backend contract is defined and built first
- Desktop helper is future/separate — no contamination into web MVP models
- Frontend must **never** contain Cloudinary or Cloudflare domain names or URL patterns
- Backend normalizes all delivery URLs before sending to frontend
- `public_url` and `thumbnail_url` are the only media URLs the frontend ever consumes

---

## Open Decisions

| # | Decision | Options | Status |
|---|----------|---------|--------|
| 1 | MVP storage backend | Local `MEDIA_ROOT` vs Cloudinary from day one | **Decided: Local first** |
| 2 | Admin API path prefix | `/api/admin/gallery/...` vs `/api/gallery/admin/...` vs `/api/gallery/manage/...` | **Decided: `/api/admin/gallery/...`** |
| 3 | Media public identifier | Integer ID vs UUID vs slug | **Decided: Integer ID** |
| 4 | Tag storage | `JSONField` vs M2M `Tag` model | **Decided: JSONField for MVP** |
| 5 | Thumbnail generation | Auto-generate on upload vs manual | **Decided: Manual/stored; auto-generate when Cloudinary ships** |
| 6 | Video in MVP scope | Fields + upload vs fields only vs defer entirely | **Decided: Fields only** |
| 7 | `public_url` storage strategy | Store in DB always vs compute for local / store for cloud | **Decided: Compute in serializer for local; store for cloud** |

---

## Recommended MVP Decisions

- Use Django's local `MEDIA_ROOT` for development; no cloud dependency in MVP
- Design `MediaItem` with `provider`, `provider_public_id`, `public_url`, `thumbnail_url` fields — provider-agnostic from day one
- `provider` choices: `local`, `cloudinary`, `cloudflare_stream` — Cloudflare Stream (video) and Cloudflare R2 (storage) are distinct products and must not share a choice value
- `media_type` field supports `image` and `video` choices from day one; video upload is out of scope for MVP
- **MVP management uses Django admin at `/admin/`** — no custom management API before public read API is proven
- Public routes use `slug` for albums, `id` (integer) for media items
- For `provider='local'`: `public_url` and `thumbnail_url` are **computed in the serializer** from `original_file.url` — not stored — to avoid stale values if `MEDIA_URL` changes
- For cloud providers: `public_url` and `thumbnail_url` are **stored at upload time** (provider-generated, stable)
- `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` must be added to `settings.py` before the first migration
- Custom management API endpoints (`/api/admin/gallery/...`) are a **later phase** — not MVP

---

## Album Model Plan

| Field | Type | Notes |
|-------|------|-------|
| `id` | Auto PK (BigAutoField) | Django default |
| `title` | `CharField(max_length=200)` | Required |
| `slug` | `SlugField(unique=True)` | Public URL identifier; must be globally unique |
| `description` | `TextField(blank=True)` | Optional |
| `is_published` | `BooleanField(default=False)` | Controls public visibility |
| `display_order` | `PositiveIntegerField(default=0)` | Manual ordering |
| `cover_media` | `ForeignKey('MediaItem', null=True, blank=True, on_delete=SET_NULL)` | Nullable; string reference `'MediaItem'` avoids circular import; SET_NULL prevents cascade on cover deletion |
| `seo_title` | `CharField(max_length=200, blank=True)` | Optional SEO override |
| `seo_description` | `TextField(blank=True)` | Optional SEO override |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

**Circular FK note:** `Album.cover_media → MediaItem` and `MediaItem.album → Album`. Both models should be defined in the same initial migration. Django resolves the internal dependency graph within a single migration file. `null=True` on `cover_media` is required.

---

## MediaItem Model Plan

| Field | Type | Notes |
|-------|------|-------|
| `id` | Auto PK (BigAutoField) | Django default |
| `album` | `ForeignKey(Album, on_delete=CASCADE, related_name='media_items')` | Required |
| `media_type` | `CharField(choices=[('image','Image'),('video','Video')], default='image')` | Explicit type from day one |
| `title` | `CharField(max_length=200, blank=True)` | Optional display title |
| `description` | `TextField(blank=True)` | Optional long description |
| `alt_text` | `CharField(max_length=500, blank=True)` | Accessibility; validate non-empty for published images in serializer |
| `caption` | `CharField(max_length=500, blank=True)` | Optional display caption |
| `tags` | `JSONField(default=list, blank=True)` | Flat tag list for MVP |
| `is_published` | `BooleanField(default=False)` | Controls public visibility |
| `display_order` | `PositiveIntegerField(default=0)` | Manual ordering within album |
| `provider` | `CharField(choices=[('local','Local'),('cloudinary','Cloudinary'),('cloudflare_stream','Cloudflare Stream')], default='local', max_length=20)` | Canonical provider; enables URL computation logic and bulk re-compute |
| `provider_public_id` | `CharField(max_length=500, blank=True)` | Cloud asset ID: Cloudinary `public_id`, Cloudflare Stream `uid`; empty for local |
| `original_file` | `FileField(upload_to='media/originals/', null=True, blank=True)` | Local dev storage; **`FileField` not `ImageField`** — Pillow is not installed |
| `public_url` | `URLField(max_length=1000, blank=True)` | Stored for cloud providers; empty for local (computed in serializer) |
| `thumbnail_url` | `URLField(max_length=1000, blank=True)` | Stored for cloud providers; empty for local (computed in serializer) |
| `width` | `PositiveIntegerField(null=True, blank=True)` | Width in px; must be set manually for local (no Pillow auto-extraction) |
| `height` | `PositiveIntegerField(null=True, blank=True)` | Height in px; must be set manually for local |
| `duration_seconds` | `FloatField(null=True, blank=True)` | Video only; `FloatField` for sub-second precision (Cloudflare Stream returns float); null for images |
| `file_size` | `PositiveIntegerField(null=True, blank=True)` | Size in bytes |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

**Fields deliberately excluded:**
- `original_url` — redundant; derivable from `original_file.url` (local) or `provider_public_id` (cloud)
- Tags as M2M — deferred until tag filtering is a real feature requirement

---

## Media Storage Strategy

### Image Strategy

| Phase | Storage | Package | Notes |
|-------|---------|---------|-------|
| MVP / Dev | Django `MEDIA_ROOT` | None | `original_file = FileField`; serializer computes `public_url` from `request.build_absolute_uri(file.url)` |
| Production | Cloudinary | `django-cloudinary-storage` or custom | `provider='cloudinary'`; `provider_public_id` = Cloudinary asset `public_id`; `public_url` stored at upload |

**Migration path:** When switching to Cloudinary, only the upload handler changes. The API contract (`public_url`, `thumbnail_url`) is identical. Frontend requires zero changes.

### Video Strategy

- `media_type='video'` choice exists in MVP model — no model migration needed when video ships
- `duration_seconds` (`FloatField`) is present from day one; null for images
- Video upload: **out of MVP scope**
- **Cloudflare Stream** is the preferred future target for video hosting, transcoding, and HLS/DASH delivery
- When video enters scope: add upload handler + Cloudflare Stream provider logic
- No video-specific model fields need to be added at that point — `provider`, `provider_public_id`, `public_url`, `thumbnail_url`, `duration_seconds` already accommodate it

---

## URL Strategy

### Public API Routes (MVP)

```
GET /api/gallery/albums/
GET /api/gallery/albums/<slug:slug>/
GET /api/gallery/albums/<slug:slug>/media/
GET /api/gallery/media/<int:id>/
```

### Management API Routes (Future Phase — after Django admin workflow is proven)

```
GET    /api/admin/gallery/albums/
POST   /api/admin/gallery/albums/
GET    /api/admin/gallery/albums/<int:id>/
PATCH  /api/admin/gallery/albums/<int:id>/
DELETE /api/admin/gallery/albums/<int:id>/

GET    /api/admin/gallery/media/
POST   /api/admin/gallery/media/
GET    /api/admin/gallery/media/<int:id>/
PATCH  /api/admin/gallery/media/<int:id>/
DELETE /api/admin/gallery/media/<int:id>/
```

**Path decisions:**
- Public uses `slug` for albums (human-readable, stable), `id` for media (simple, no slug needed)
- Management API always uses `id` — management operations reference internal IDs
- `/api/admin/gallery/...` reserved for future custom management API; does **not** conflict with Django's `/admin/` (which has no `/api/` prefix)
- `config/urls.py` should include DRF router registrations under the `api/` prefix when public routes are built
- **Do not build the management API routes before Django admin + public API are both working**

---

## Public API Contract Plan

### `GET /api/gallery/albums/` — Album list item

```json
{
  "id": 1,
  "slug": "wildlife",
  "title": "Wildlife",
  "description": "Animal photography",
  "display_order": 0,
  "cover": {
    "id": 10,
    "thumbnail_url": "https://...",
    "alt_text": "Fox in forest"
  }
}
```

### `GET /api/gallery/albums/<slug>/` — Album detail

```json
{
  "id": 1,
  "slug": "wildlife",
  "title": "Wildlife",
  "description": "Animal photography",
  "seo_title": "Wildlife Photography",
  "seo_description": "Beautiful animal photography from around the world",
  "display_order": 0,
  "cover": {
    "id": 10,
    "thumbnail_url": "https://...",
    "alt_text": "Fox in forest"
  },
  "created_at": "2026-01-01T00:00:00Z"
}
```

### `GET /api/gallery/media/<id>/` — MediaItem (public)

```json
{
  "id": 10,
  "album_slug": "wildlife",
  "media_type": "image",
  "title": "Fox in forest",
  "description": "",
  "alt_text": "Fox standing in forest",
  "caption": "",
  "tags": [],
  "public_url": "https://...",
  "thumbnail_url": "https://...",
  "width": 1600,
  "height": 1000,
  "display_order": 0
}
```

**Deliberately excluded from public response:** `provider`, `provider_public_id`, `original_file`, `file_size`, `duration_seconds` (add to public response when video ships), `is_published`, `created_at`, `updated_at`

---

## Admin API Contract Plan (Future Phase)

> **Not part of MVP.** Management in MVP is handled through Django admin at `/admin/`. Custom management API endpoints are only needed if Django admin becomes insufficient for the workflow.

### Admin MediaItem (additional fields over public shape — for reference)

```json
{
  "id": 10,
  "album": 1,
  "album_slug": "wildlife",
  "media_type": "image",
  "title": "Fox in forest",
  "description": "",
  "alt_text": "Fox standing in forest",
  "caption": "",
  "tags": [],
  "is_published": false,
  "display_order": 0,
  "provider": "local",
  "provider_public_id": "",
  "public_url": "http://localhost:8000/media/originals/fox.jpg",
  "thumbnail_url": "http://localhost:8000/media/originals/fox.jpg",
  "width": 1600,
  "height": 1000,
  "file_size": 245000,
  "duration_seconds": null,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

Admin album shape includes `is_published`, `seo_title`, `seo_description`, `cover_media` as an ID (not nested), all timestamps.

**Trigger for building this:** Django admin is not usable for the actual operator (e.g. too technical for non-developer users). Until that threshold is reached, Django admin is sufficient.

---

## Frontend Contract Rules

1. Frontend renders `public_url` and `thumbnail_url` as-is — no URL construction
2. Frontend never reads `provider`, `provider_public_id`, or `original_file`
3. Frontend navigates albums via `slug` (e.g. `/gallery/wildlife`)
4. Frontend navigates media items via `id` (e.g. `/photos/10`)
5. Frontend uses `album_slug` in the media response to navigate back — no extra requests needed
6. Public endpoints return only `is_published: true` records — client-side filtering is never needed
7. If a field is absent from the public API, frontend treats it as empty — no fallback URL construction

---

## Canonical Truth Rules

1. `MediaItem.public_url` and `MediaItem.thumbnail_url` are the **only** URLs the frontend ever consumes
2. For `provider='local'`: serializer computes these at response time via `request.build_absolute_uri(original_file.url)` — not stored in DB
3. For `provider='cloudinary'` / `provider='cloudflare_stream'`: stored in DB at upload time (provider-generated, stable)
4. `provider` field is the machine-readable record of where the asset lives — it drives URL computation logic and any bulk refresh
5. `provider_public_id` is the cloud asset handle — it enables Cloudinary and Cloudflare Stream API operations without parsing stored URLs
6. If a provider changes its delivery domain, a management command updates `public_url` for affected records — the API contract is unchanged

---

## Future Desktop Helper Compatibility

- Desktop helper is out of MVP scope
- When it ships: it will call the same admin API endpoints (`POST /api/admin/gallery/media/`)
- The `provider` + `provider_public_id` pattern accommodates the "upload happened in desktop app, register to backend" workflow — desktop helper can upload directly to Cloudinary and POST the `provider_public_id` to the backend
- No special model fields or endpoints need to be reserved in MVP for this use case

---

## What Not To Build Yet

- Custom management API endpoints (`/api/admin/gallery/...`) — use Django admin first
- JWT or session auth endpoints for a custom management UI
- Custom upload endpoint — Django admin file upload is sufficient for MVP
- Video upload or Cloudflare Stream integration
- Cloudinary package installation or settings
- Tag filtering endpoints
- Search or filter on albums or media
- Desktop helper endpoints
- Frontend files of any kind
- Thumbnail auto-generation pipeline
- Pillow or any image processing package
- AI processing of any kind

---

## Risks / Tradeoffs

| Risk | Tradeoff | Mitigation |
|------|----------|------------|
| `cover_media` circular FK | Album and MediaItem reference each other | `null=True`, `SET_NULL`, string FK `'MediaItem'`; both in same initial migration |
| Local `public_url` not stored | Serializer must compute URL per request for local provider | Negligible cost for local dev; eliminated when cloud provider ships |
| Cloudflare product ambiguity | `cloudflare` is too vague — R2 vs Stream are distinct | Use `cloudflare_stream` as the choice value from day one |
| `duration_seconds` precision | Integer truncates sub-second video duration | Use `FloatField` — Cloudflare Stream returns float |
| No Pillow installed | Cannot use `ImageField`; no auto width/height extraction | Use `FileField`; populate dimensions manually or via upload handler |
| JSONField tags | No indexed tag filtering | Acceptable for MVP; M2M migration is non-breaking when needed |
| Integer ID for media public route | Sequential IDs are enumerable | Acceptable for public content on a photography platform |
| `DEFAULT_AUTO_FIELD` not set | System check warning on `makemigrations` | Add `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` to `settings.py` before first migration |

---

## MVP Admin Strategy

- MVP management uses Django admin at `/admin/` — no custom management API before public read API is proven
- The first admin user is a superuser created via `python manage.py createsuperuser`
- Django admin is acceptable for MVP because it avoids building custom auth and admin UI too early
- Django admin is for **internal management only** — public visitors never access it
- Public frontend only consumes published content from public API endpoints
- A custom simple admin dashboard can be built later if Django admin is too technical for the operator
- No JWT, no session auth endpoints, no custom upload endpoint are needed while Django admin is the management tool

---

## Final Recommended Implementation Order

```
1.  Add DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' to config/settings.py
    if not already set.

2.  Implement Album and MediaItem models in gallery/models.py
    (provider choices: local / cloudinary / cloudflare_stream,
     duration_seconds as FloatField,
     original_file as FileField).

3.  Register Album and MediaItem in gallery/admin.py.

4.  Run makemigrations and migrate.

5.  Run python manage.py check — confirm zero errors or warnings.

6.  Create a superuser if one does not already exist:
      python manage.py createsuperuser

7.  Validate in Django admin:
      - create an album
      - upload a local image
      - set is_published
      - set cover_media if available
      - confirm records save cleanly

8.  Build public read serializers:
      AlbumListSerializer, AlbumDetailSerializer, MediaItemPublicSerializer.
    Serialize public_url and thumbnail_url via serializer method fields
    (compute from original_file for local; read stored field for cloud).

9.  Build public read views with is_published=True queryset filter.

10. Create gallery/urls.py with public routes only.

11. Wire config/urls.py to include public gallery API routes under /api/.

12. Validate public API returns only is_published=True records.

13. Build frontend public gallery display.

14. Only after public MVP works, decide whether a custom management API is needed.

15. Build custom management API / admin dashboard only if Django admin is not
    simple enough for the operator.

16. Add Cloudinary before production image hosting if needed.

17. Add AI processing later — not in MVP.

18. Add Cloudflare Stream only when video upload enters scope.
```
