# Backend Scalability & Pagination Audit

**Date:** 2026-06-05
**Status:** Audit only — no code changed.

---

## Executive Summary

The backend is clean and well-structured for its current scale, but has four
critical gaps that must be closed before the public frontend builds gallery
browsing features:

1. **No pagination anywhere.** Every list endpoint returns an unbounded
   queryset. `REST_FRAMEWORK` pagination settings are absent from
   `config/settings.py`.
2. **Public video and album endpoints are mixed with admin endpoints** in
   `gallery/urls.py`. There is no dedicated paginated public video browse
   endpoint.
3. **`VideoClipSerializer` is a single all-purpose serializer** used for
   public list, public detail, upload responses, and admin sync. It includes
   `description_bs`, `description_en`, `updated_at`, `is_public`, and both
   raw title fields in every list response.
4. **Critical indexes are missing on `VideoClip`** — the model has no
   indexes at all.

All other areas (query optimization, language support, media storage, access
control) are in reasonable shape but have targeted improvements needed.

---

## Current Architecture

### URL prefix map

| Prefix | File | Audience |
|---|---|---|
| `/api/auth/` | `auth_api/urls.py` | Auth (login/logout/session/csrf) |
| `/api/gallery/` | `gallery/urls.py` | Mixed public+admin endpoints |
| `/api/public/` | `gallery/public_urls.py` | Public-only endpoints |

### Application stack

- Django 6.0.5, DRF (no version pinned in visible code)
- SQLite locally, PostgreSQL on Heroku (via `dj_database_url`)
- Cloudflare Stream — video hosting / direct upload
- Cloudflare Images — image hosting
- Local file storage fallback for both

---

## Current Media Models

### `Tag` (`gallery/models.py:7`)

| Field | Type | Notes |
|---|---|---|
| `name_bs` | CharField(100) | Primary language |
| `name_en` | CharField(100, blank) | |
| `slug` | SlugField(120, unique) | Auto-indexed (unique) |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

`Meta.ordering = ['slug']`. No explicit `indexes`. `slug` has an implicit
unique index.

---

### `Album` (`gallery/models.py:27`)

| Field | Type | Notes |
|---|---|---|
| `title` | CharField(200, blank) | Legacy/unused |
| `slug` | SlugField(unique) | Auto-indexed (unique) |
| `gallery_type` | CharField(10, choices) | `image` or `video` |
| `description` | TextField(blank) | Legacy/unused |
| `is_published` | BooleanField(default=False) | Public visibility gate |
| `display_order` | PositiveIntegerField(default=0) | Sort key |
| `cover_media` | FK → MediaItem (null, SET_NULL) | |
| `title_en` | CharField(200, blank) | |
| `title_bs` | CharField(200, blank) | Primary language |
| `description_en` | TextField(blank) | |
| `description_bs` | TextField(blank) | Primary language |
| `seo_title_en/bs` | CharField(200, blank) each | |
| `seo_description_en/bs` | TextField(blank) each | |
| `tags` | M2M → Tag | |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

`Meta.ordering = ['display_order', 'title_en', 'title']`.

**No explicit `indexes` block.** Only `slug` has an implicit unique index.
`is_published` and `gallery_type` have no indexes.

**No `published_at` field** — album has no timestamp for when it was published.

---

### `MediaItem` (`gallery/models.py:79`)

| Field | Type | Notes |
|---|---|---|
| `album` | FK → Album (CASCADE) | |
| `media_type` | CharField(10, choices) | `image` or `video` |
| `title/description/alt_text/caption` | Legacy blank fields | |
| `tags` | JSONField(default=list) | **Not M2M — unindexed** |
| `is_published` | BooleanField(default=False) | Public visibility gate |
| `display_order` | PositiveIntegerField(default=0) | |
| `title_en/bs`, `description_en/bs`, `alt_text_en/bs`, `caption_en/bs` | Various bilingual fields | |
| `provider` | CharField(20, choices) | `local`, `cloudinary`, `cloudflare_images`, `cloudflare_stream` |
| `provider_public_id` | CharField(500, blank) | |
| `original_file` | ImageField (null, blank) | Local only |
| `public_url` | URLField(1000, blank) | Cloud providers |
| `thumbnail_url` | URLField(1000, blank) | |
| `width`, `height` | PositiveIntegerField (null) | |
| `duration_seconds` | FloatField (null) | |
| `file_size` | PositiveIntegerField (null) | |
| `created_at`, `updated_at` | DateTimeField | |

`Meta.ordering = ['display_order', 'id']`.

**No explicit `indexes` block.** `album` FK has an implicit index (Django
creates it for FKs). `is_published` has no index.

---

### `VideoClip` (`gallery/models.py:212`)

| Field | Type | Notes |
|---|---|---|
| `album` | FK → Album (null, SET_NULL) | Optional gallery assignment |
| `title_bs` | CharField(255) | Required |
| `title_en` | CharField(255, blank) | |
| `description_bs` | TextField(blank) | |
| `description_en` | TextField(blank) | |
| `cloudflare_uid` | CharField(128, unique) | Auto-indexed (unique) |
| `cloudflare_thumbnail_url` | URLField(blank) | Stored; no provider call needed |
| `cloudflare_playback_url` | URLField(blank) | Stored; no provider call needed |
| `duration_seconds` | PositiveIntegerField (null) | |
| `status` | CharField(32, choices) | `uploading`, `processing`, `ready`, `failed` |
| `is_public` | BooleanField(default=False) | Public visibility gate |
| `tags` | M2M → Tag | |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

`Meta.ordering = ['-created_at']`.

**No `indexes` block.** `cloudflare_uid` has an implicit unique index.
`is_public`, `status`, and `album` FK have no explicit indexes.

**No `published_at` field.** `created_at` is the only timestamp.

**Critical gap:** `is_public` and `status` are the two primary public-browse
filters. The combination `(is_public, status)` has no index. Every public
query scans the full table.

---

### `VisitorMessage` (`gallery/models.py:246`)

Private messaging, not part of public browsing.

Explicit indexes: `status`, `created_at`, `sender_email`
(`gallery/migrations/0012_visitor_message_video_context.py:24-34`).

---

### `VideoTimestampComment` (`gallery/models.py:305`)

Public comments, admin-moderated.

Explicit indexes: `(video, status)`, `status`, `created_at`
(`gallery/migrations/0013_video_timestamp_comment.py:29`).

---

## Existing Public Endpoints

### `/api/public/` — `gallery/public_urls.py`

#### `GET /api/public/hero-video/`
- **View:** `HeroVideoView` (`gallery/views.py:862`)
- **Serializer:** `HeroVideoSerializer`
- **Queryset:** `VideoClip.objects.select_related('album').filter(is_public=True, status='ready').order_by('-created_at').first()`
- **Auth:** `AllowAny`
- **Pagination:** None — returns single object
- **Filters:** None — always latest ready public clip
- **Response weight:** Lightweight — 11 fields including album title fields via
  `get_album_title_bs/en` methods. **Uses `select_related('album')`.**
- **Risk:** None. Single-row lookup.

#### `POST /api/public/messages/`
- **View:** `VisitorMessageCreateView` (`gallery/views.py:895`)
- **Serializer:** `VisitorMessageCreateSerializer`
- **Auth:** `AllowAny`
- **Pagination:** N/A — write-only

#### `GET/POST /api/public/videos/<video_pk>/comments/`
- **View:** `VideoTimestampCommentListCreateView` (`gallery/views.py:907`)
- **Read serializer:** `VideoTimestampCommentPublicSerializer` (5 fields)
- **Write serializer:** `VideoTimestampCommentCreateSerializer`
- **Queryset (GET):** `VideoTimestampComment.objects.filter(video_id=video_pk, status='approved')` — no `select_related`, no pagination
- **Auth:** `AllowAny`
- **Pagination:** **None — unbounded.** A popular video could accumulate thousands of approved comments.
- **Risk:** Medium. No pagination, no `select_related('video')`.

---

### `/api/gallery/` — `gallery/urls.py` (public endpoints mixed in)

#### `GET /api/gallery/albums/`
- **View:** `AlbumListCreateView` (`gallery/views.py:57`)
- **Serializer (GET):** `AlbumListSerializer`
- **Queryset:** `Album.objects.filter(is_published=True).prefetch_related('tags')`
- **Auth:** `AllowAny` (GET), `IsAdminUser` (POST)
- **Pagination:** **None — returns all published albums.**
- **Filters:** `?tag=<slug>`, `?search=<query>` (searches `title_bs`, `title_en`, `description_bs`, `description_en`, tag name/slug)
- **Response:** 7 fields — `id`, `slug`, `title` (lang-resolved), `description` (lang-resolved), `display_order`, `cover` (nested `MediaCoverSerializer`), `tags` (nested `TagSerializer` array). **`prefetch_related('tags')` exists; `cover_media` is NOT prefetched.**
- **Risk:** `cover_media` (FK to `MediaItem`) triggers a per-album query. N+1 for cover images.

#### `GET /api/gallery/albums/<slug>/`
- **View:** `AlbumRetrieveUpdateDestroyView`
- **Serializer (GET):** `AlbumDetailSerializer`
- **Queryset:** `Album.objects.filter(is_published=True)` — no `select_related`, no `prefetch_related`
- **Auth:** `AllowAny` (GET)
- **Pagination:** N/A — single object
- **Risk:** Tags accessed without `prefetch_related`.

#### `GET /api/gallery/albums/<slug>/media/`
- **View:** `AlbumMediaListCreateView`
- **Serializer (GET):** `MediaItemPublicSerializer`
- **Queryset:** `MediaItem.objects.filter(album=album, is_published=True)` — no `select_related`
- **Auth:** `AllowAny` (GET)
- **Pagination:** **None — returns all published media items in album.**
- **Filters:** None
- **Response:** 12 fields. `album_slug` uses `SlugRelatedField(source='album', slug_field='slug')` — touches album FK **without `select_related`**. Per-item query for `album`.
- **Risk:** N+1 on `album` for every media item in list.

#### `GET /api/gallery/videos/`
- **View:** `VideoClipListView` (`gallery/views.py:281`)
- **Serializer:** `VideoClipSerializer`
- **Queryset:** `VideoClip.objects.select_related('album').prefetch_related('tags').filter(is_public=True, status='ready')` (public), all clips (staff)
- **Auth:** `AllowAny` — staff check done inside `get_queryset`
- **Pagination:** **None — returns all matching videos.**
- **Filters:** `?album=<pk>`, `?tag=<slug>`, `?search=<query>` (6 fields searched)
- **Response:** 14 fields including `description_bs`, `description_en`, `updated_at`, `is_public`, `status` — full model dump via `VideoClipSerializer`. Tags array (nested).
- **Risk:** Most critical scalability risk. No pagination. Returns descriptions in list view.

#### `GET /api/gallery/videos/<pk>/`
- **View:** `VideoClipDetailView`
- **Serializer:** `VideoClipSerializer` — **same serializer as list view**
- **Auth:** `AllowAny`
- **Pagination:** N/A — single object

#### `GET /api/gallery/field-notes/`
- **View:** `FieldNoteListView`
- **Serializer:** `FieldNoteListSerializer`
- **Queryset:** `FieldNote.objects.filter(is_published=True)` — no `select_related`
- **Auth:** `AllowAny`
- **Pagination:** **None.**
- **Risk:** `cover_image` FK accessed without `select_related`. N+1 per note.

#### `GET /api/gallery/field-notes/<slug>/`
- **View:** `FieldNoteDetailView`
- **Serializer:** `FieldNoteDetailSerializer`
- **Queryset:** `FieldNote.objects.filter(is_published=True)` — no `select_related`
- **Risk:** `cover_image` FK accessed without `select_related`.

---

## Existing Admin/Internal Endpoints

All admin endpoints require `IsAdminUser` (`is_staff=True`).

| URL | View | Serializer (GET / WRITE) | Pagination |
|---|---|---|---|
| `GET/POST /api/gallery/admin/tags/` | `AdminTagListCreateView` | `TagSerializer` / `TagWriteSerializer` | **None** |
| `GET/PATCH/DELETE /api/gallery/admin/tags/<pk>/` | `AdminTagRetrieveUpdateDestroyView` | same | N/A |
| `GET/POST /api/gallery/admin/image-galleries/` | `AdminImageGalleryListCreateView` | `AdminImageGallerySerializer` / Write | **None** |
| `GET/PATCH/DELETE /api/gallery/admin/image-galleries/<pk>/` | `AdminImageGalleryRetrieveUpdateDestroyView` | same | N/A |
| `GET/POST /api/gallery/admin/images/` | `AdminImageItemListCreateView` | `AdminImageItemSerializer` / Write | **None** |
| `GET/PATCH/DELETE /api/gallery/admin/images/<pk>/` | `AdminImageItemRetrieveUpdateDestroyView` | same | N/A |
| `GET/POST /api/gallery/admin/video-galleries/` | `AdminVideoGalleryListCreateView` | `AdminVideoGallerySerializer` / Write | **None** |
| `GET/PATCH/DELETE /api/gallery/admin/video-galleries/<pk>/` | ditto | same | N/A |
| `GET /api/gallery/admin/videos/` | `AdminVideoItemListView` | `AdminVideoItemSerializer` | **None** |
| `POST /api/gallery/admin/videos/direct-upload/` | `AdminVideoDirectUploadView` | `AdminVideoDirectUploadSerializer` | N/A |
| `POST /api/gallery/admin/videos/complete-upload/` | `AdminVideoCompleteUploadView` | `AdminVideoCompleteUploadSerializer` | N/A |
| `GET/PATCH/DELETE /api/gallery/admin/videos/<pk>/` | `AdminVideoItemRetrieveUpdateDestroyView` | `AdminVideoItemSerializer` / Write | N/A |
| `POST /api/gallery/admin/videos/<pk>/refresh-status/` | `AdminVideoRefreshStatusView` | `AdminVideoItemSerializer` | N/A |
| `POST /api/gallery/admin/visitor-messages/<pk>/reply/` | `VisitorMessageReplyView` | `VisitorMessageReplyRequestSerializer` | N/A |

**None of the admin list endpoints are paginated.**

### Upload and Processing Lifecycle (`gallery/views.py:208–278`, `gallery/services/cloudflare_stream.py`)

1. Admin calls `POST /api/gallery/admin/videos/direct-upload/` (or the legacy `/api/gallery/videos/direct-upload/`).
2. Backend calls Cloudflare Stream `create_direct_upload` API; receives `uid` + `upload_url`.
3. `VideoClip` is created with `status='uploading'`, `is_public=True` (**default public from the first moment**).
4. Frontend uploads video bytes directly to Cloudflare via `upload_url`.
5. Admin calls `POST /api/gallery/admin/videos/complete-upload/` → status set to `'processing'`.
6. Cloudflare processes the video asynchronously.
7. Admin calls `POST /api/gallery/admin/videos/<pk>/refresh-status/` → backend calls `get_video_details`, maps Cloudflare state to `ready`/`failed`, saves `duration_seconds`, `cloudflare_playback_url`, `cloudflare_thumbnail_url`.
8. No webhook or polling mechanism exists — admin must manually trigger refresh.

**Gap:** `is_public=True` is set at creation time (`gallery/views.py:253`: `is_public=True`), before the video is ready. Public endpoints filter `status='ready'`, so the video is invisible until ready — but `is_public` is already `True`. Admin must manually set `is_public=False` to hide a video, even after it fails.

**Gap:** No automatic status transition. No webhook listener. No `is_public=False` on `status='failed'`.

---

## Current Pagination Behavior

**`REST_FRAMEWORK` settings block is absent from `config/settings.py`.**

DRF defaults apply:
- `DEFAULT_PAGINATION_CLASS`: `None`
- `PAGE_SIZE`: `None`

**Every list endpoint is unpaginated and returns all matching rows.**

No per-view `pagination_class` override exists on any view in `gallery/views.py`.

This is the top scalability risk in the project.

---

## Current Query Performance Risks

### `GET /api/gallery/videos/` — `VideoClipListView`

```python
# gallery/views.py:291
VideoClip.objects.select_related('album').prefetch_related('tags').all()
```

- `select_related('album')` ✅
- `prefetch_related('tags')` ✅
- **No pagination** — returns all rows matching filter ❌
- **No index on `(is_public, status)`** — full table scan for public filter ❌
- `VideoClipSerializer` includes `description_bs`, `description_en` in list ❌

---

### `GET /api/gallery/albums/` — `AlbumListCreateView`

```python
# gallery/views.py:69
Album.objects.filter(is_published=True).prefetch_related('tags')
```

- `prefetch_related('tags')` ✅
- `select_related('cover_media')` **missing** ❌ — `AlbumListSerializer` uses `MediaCoverSerializer(source='cover_media')` which reads `cover_media.thumbnail_url` and `cover_media.original_file`. Without `select_related`, each album in the list triggers a separate query for its cover.
- No pagination ❌

---

### `GET /api/gallery/albums/<slug>/media/` — `AlbumMediaListCreateView`

```python
# gallery/views.py:132
MediaItem.objects.filter(album=album, is_published=True)
```

- No `select_related` ❌ — `MediaItemPublicSerializer` uses `album_slug = SlugRelatedField(source='album', ...)` which hits the `album` FK per item.
- No pagination ❌

---

### `GET /api/gallery/albums/<slug>/` — `AlbumRetrieveUpdateDestroyView`

```python
# gallery/views.py:108
Album.objects.filter(is_published=True)
```

- No `select_related('cover_media')` ❌ — `AlbumDetailSerializer` uses `MediaCoverSerializer(source='cover_media')`.
- No `prefetch_related('tags')` ❌ — `AlbumDetailSerializer` uses `tags = TagSerializer(many=True, ...)`.

---

### `GET /api/gallery/field-notes/` — `FieldNoteListView`

```python
# gallery/views.py:161
FieldNote.objects.filter(is_published=True)
```

- `FieldNoteListSerializer` uses `cover_image = FieldNoteCoverSerializer(read_only=True)` — FK hit per note. No `select_related`. ❌

---

### `GET /api/gallery/admin/images/` — `AdminImageItemListCreateView`

```python
# gallery/views.py:690
MediaItem.objects.filter(media_type='image', album__gallery_type='image').select_related('album')
```

- `select_related('album')` ✅
- No pagination ❌

---

### `GET /api/gallery/admin/videos/` — `AdminVideoItemListView`

```python
# gallery/views.py:750
VideoClip.objects.select_related('album').all()
```

- `select_related('album')` ✅
- `prefetch_related('tags')` **missing** ❌ — `AdminVideoItemSerializer` uses `tags = TagSerializer(many=True, ...)` which hits the M2M per video.
- No pagination ❌

---

### `GET /api/public/videos/<video_pk>/comments/`

```python
# gallery/views.py:918
VideoTimestampComment.objects.filter(video_id=video_pk, status='approved')
```

- No `select_related` ❌ (though `VideoTimestampCommentPublicSerializer` only needs the comment's own fields — acceptable)
- No pagination ❌

---

## Current Database Indexes

### Confirmed by migrations

| Model | Indexed fields | Source |
|---|---|---|
| `Album` | `slug` (unique) | `0001_initial.py` implicit |
| `Album` | `gallery_type` | **None** |
| `Album` | `is_published` | **None** |
| `MediaItem` | `album` FK | Django auto-creates FK index |
| `MediaItem` | `is_published` | **None** |
| `VideoClip` | `cloudflare_uid` (unique) | `0008_videoclip.py` implicit |
| `VideoClip` | `album` FK | Django auto-creates FK index |
| `VideoClip` | `is_public` | **None** |
| `VideoClip` | `status` | **None** |
| `VideoClip` | `(is_public, status)` | **None** |
| `VideoClip` | `created_at` | **None** |
| `Tag` | `slug` (unique) | `0010_tags_and_m2m.py` implicit |
| `VisitorMessage` | `status`, `created_at`, `sender_email` | `0012_visitor_message_video_context.py` |
| `VideoTimestampComment` | `(video, status)`, `status`, `created_at` | `0013_video_timestamp_comment.py` |

### Missing indexes

| Model | Missing index | Query that needs it |
|---|---|---|
| `VideoClip` | `(is_public, status)` | Every public video list/detail/hero query |
| `VideoClip` | `(is_public, status, created_at)` | Cursor pagination on public video list |
| `VideoClip` | `created_at` | Default ordering `-created_at` |
| `Album` | `is_published` | Every public album query |
| `Album` | `(is_published, gallery_type)` | Admin gallery queries |
| `Album` | `(is_published, display_order)` | Public album ordering |
| `MediaItem` | `(album, is_published)` | Album media list |
| `FieldNote` | `is_published` | Public field-note list |
| `FieldNote` | `(is_published, published_at)` | Ordered public field-note list |

---

## Serializer & Import Discipline Audit

### File: `gallery/serializers.py` — top-level import

```python
from .models import Album, FieldNote, MediaItem, Tag, VideoClip,
                    VideoTimestampComment, VisitorMessage, VisitorMessageReply
```

All models are imported at the top. `VisitorMessageReply` is imported but not
used by any serializer (only by the view). Acceptable for now but could be
narrowed.

---

### `VideoClipSerializer` — used everywhere

**Used by:** `VideoClipListView` (public list), `VideoClipDetailView` (public
detail), `VideoClipDirectUploadView` (upload response), `VideoClipSyncView`
(sync response), `HeroVideoView` uses a separate `HeroVideoSerializer`.

**Fields returned:**
```
id, album, title_bs, title_en, description_bs, description_en,
cloudflare_uid, cloudflare_thumbnail_url, cloudflare_playback_url,
duration_seconds, status, is_public, tags (nested), created_at, updated_at
```

**Problems:**
- `description_bs` and `description_en` are full `TextField` values — sent in
  every list response. A card serializer should omit them.
- `album` is sent as a raw integer PK only (bare `IntegerField`) — no album
  title or slug. Frontend cannot build album context without a second request.
  However this is inconsistent with admin serializers that include
  `gallery_title_bs`.
- `is_public` and `status` are internal state fields — not needed by public
  consumers.
- `updated_at` is not needed by public consumers.
- `tags` uses nested `TagSerializer(many=True)` — requires `prefetch_related('tags')` in the view. List view has this (`VideoClipListView`); detail view (`VideoClipDetailView`) does not call `prefetch_related('tags')` explicitly (relies on queryset default).
- No language selection (`?lang=`). Returns both `title_bs` and `title_en`
  always, unlike the album/field-note serializers which resolve language.

---

### `AlbumListSerializer` — public album list

**Fields:** `id`, `slug`, `title` (lang-resolved), `description`
(lang-resolved), `display_order`, `cover` (nested `MediaCoverSerializer`),
`tags` (nested `TagSerializer` array).

**Assessment:** Reasonable for a card. Returns both `description` resolved to
one language. No descriptions in both languages. Cover is a minimal 3-field
nested object. Tags are 4-field objects.

**Gap:** View does not `select_related('cover_media')`. Every album in the list
triggers a cover query. Fix: add `.select_related('cover_media')` to the
`get_queryset` in `AlbumListCreateView`.

---

### `AlbumDetailSerializer` — public album detail

**Fields:** `id`, `slug`, `title`, `description`, `seo_title`,
`seo_description`, `display_order`, `cover` (nested), `tags` (nested),
`created_at`.

**Assessment:** Appropriate for a detail page. Does not include media items
(those are fetched separately via `/albums/<slug>/media/`).

**Gap:** View queryset has no `select_related('cover_media')` or
`prefetch_related('tags')`.

---

### `MediaItemPublicSerializer` — album media list

**Fields:** `id`, `album_slug`, `media_type`, `title`, `description`,
`alt_text`, `caption`, `tags`, `public_url`, `thumbnail_url`, `width`,
`height`, `display_order`.

**Gap:** `album_slug = SlugRelatedField(source='album', slug_field='slug')` —
reads album FK per item. View does not `select_related('album')`.

`tags` is a `JSONField` (not M2M) on `MediaItem` — no join needed. Acceptable.

---

### `AdminVideoItemSerializer` — admin video list/detail

**Fields:** `id`, `gallery_id`, `gallery_slug`, `gallery_title_bs`,
`title_bs`, `title_en`, `description_bs`, `description_en`, `cloudflare_uid`,
`cloudflare_thumbnail_url`, `cloudflare_playback_url`, `duration_seconds`,
`status`, `is_published`, `tags` (nested), `created_at`, `updated_at`.

**Gap:** `AdminVideoItemListView` uses `select_related('album')` ✅ but no
`prefetch_related('tags')` ❌ — N+1 on tags for every video in list.

---

### `HeroVideoSerializer` — public hero

**Fields:** `id`, `title_bs`, `title_en`, `album_id`, `album_title_bs`,
`album_title_en`, `duration_seconds`, `cloudflare_uid`,
`cloudflare_playback_url`, `cloudflare_thumbnail_url`.

**Assessment:** Clean single-purpose serializer. View uses
`select_related('album')`. Uses method fields `get_album_title_bs/en` instead
of nested serializer — correct approach.

---

### Recommended Serializer Split

| Serializer | Purpose |
|---|---|
| `PublicVideoCardSerializer` | Public list — id, title (1 lang), thumbnail, duration, uid, album_id, album_title |
| `PublicVideoDetailSerializer` | Public detail — adds description (1 lang), tags |
| `VideoClipSerializer` | Keep for admin/upload responses (or rename to `AdminVideoUploadSerializer`) |
| `PublicAlbumCardSerializer` | Already close to `AlbumListSerializer` — needs `select_related` fix |
| `PublicAlbumDetailSerializer` | Already `AlbumDetailSerializer` — needs queryset fix |

The most impactful split is `PublicVideoCardSerializer` to stop sending
`description_bs/en` in every video list row.

---

## Additional Scope-Affecting Areas

### Public/Private Boundary

There is no custom queryset manager or shared helper for "public-ready video".
Each view independently re-implements the filter:
```python
# VideoClipListView: gallery/views.py:296-297
qs.filter(is_public=True, status=VideoClip.STATUS_READY)

# VideoClipDetailView: gallery/views.py:315-317
VideoClip.objects.select_related('album').filter(is_public=True, status=VideoClip.STATUS_READY)

# HeroVideoView: gallery/views.py:869
VideoClip.objects.select_related('album').filter(is_public=True, status=VideoClip.STATUS_READY)
```

No `published_at` field exists on `VideoClip` or `Album`. "Published at" is
currently implied by `created_at` (for videos) or unavailable (for albums).

A future `VideoClip.objects.public_ready()` custom manager method would
centralize this filter. Not yet implemented.

---

### Upload Lifecycle

| Status | Meaning | Set by |
|---|---|---|
| `uploading` | Direct upload in progress | `VideoClip.objects.create()` in `AdminVideoDirectUploadView` and `VideoClipDirectUploadView` |
| `processing` | Frontend notified upload complete | `AdminVideoCompleteUploadView` |
| `ready` | Cloudflare confirmed ready | `AdminVideoRefreshStatusView` / `VideoClipSyncView` |
| `failed` | Cloudflare reported failure | `AdminVideoRefreshStatusView` / `VideoClipSyncView` |

**Gaps:**
- `is_public` defaults to `True` at creation time. A video in `uploading` or
  `failed` state is already `is_public=True`, but `status != 'ready'` prevents
  it from appearing publicly. However, if an admin later calls
  `PATCH /admin/videos/<pk>/` to set `is_published=True` after the fact, there
  is no guard requiring `status='ready'`.
- No webhook. Status refresh is manual only.
- Failed uploads are not automatically hidden or cleaned up.
- `cloudflare_uid` uniqueness (`unique=True`) means a failed upload's record
  blocks re-use of that UID.

---

### Thumbnail and Card Metadata Strategy

`VideoClip` stores all card-display fields in the database:
- `cloudflare_thumbnail_url` — stored after `refresh-status` ✅
- `cloudflare_playback_url` — stored after `refresh-status` ✅
- `cloudflare_uid` — stored at creation ✅
- `duration_seconds` — stored after `refresh-status` ✅
- `title_bs`, `title_en` — stored at creation ✅
- `album` FK (for title) — `select_related` available ✅

**No provider API calls are needed at public request time.** Public video cards
can be built entirely from database fields.

`cloudflare_thumbnail_url` may be empty if `refresh-status` was never called or
if `CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN` was not set when sync ran.

---

### Populated Albums / Galleries

No endpoint or queryset exists to return only albums that contain at least one
public-ready media item or video. The current `AlbumListCreateView` returns all
published albums regardless of whether they have any content.

A future annotated query such as:
```python
Album.objects.filter(is_published=True).annotate(
    public_video_count=Count('videos', filter=Q(
        videos__is_public=True, videos__status='ready'
    ))
).filter(public_video_count__gt=0)
```
is not yet implemented. The frontend currently receives empty published albums.

---

### Language and Translation Shape

The `LangContextMixin` (`gallery/views.py:52–57`) injects `lang` into
serializer context from `?lang=` query parameter (defaults to `en`, accepts
`bs`).

Serializers that use `resolve_translated(obj, field_name, lang)` return a
single resolved field as `title` and `description` — correct for public
responses.

**Affected serializers:** `AlbumListSerializer`, `AlbumDetailSerializer`,
`MediaItemPublicSerializer`, `FieldNoteListSerializer`,
`FieldNoteDetailSerializer`, `MediaCoverSerializer`.

**Not affected:** `VideoClipSerializer` — returns both `title_bs` and
`title_en` raw, no lang resolution. This is inconsistent with albums.

**`LangContextMixin` is not applied** to `VideoClipListView` or
`VideoClipDetailView`. If a `PublicVideoCardSerializer` is introduced, it
should receive lang context or resolve the field itself.

---

### Comments and Timestamps Payload Risk

`VideoClipSerializer` does **not** include comments, timestamp comments,
visitor messages, or related videos. Only the direct model fields + nested
tags are returned. ✅

`VideoTimestampCommentListCreateView` is a separate endpoint at
`/api/public/videos/<pk>/comments/` — comments are not embedded in video
responses. ✅

No `VisitorMessage` data is ever returned in public responses. ✅

---

### Search Strategy

`VideoClipListView` and `AlbumListCreateView` both implement `?search=` via
Django ORM `__icontains` on multiple fields joined with `Q(...)`.

The video search covers: `title_bs`, `title_en`, `description_bs`,
`description_en`, `album.title_bs`, `album.title_en`, `tags.name_bs`,
`tags.name_en`, `tags.slug`. All filtering happens in the database. ✅

The album search covers: `title_bs`, `title_en`, `description_bs`,
`description_en`, `tags.name_bs`, `tags.name_en`, `tags.slug`. ✅

**Gaps:**
- `__icontains` on PostgreSQL is not using full-text search indexes. It falls
  back to `LIKE '%query%'` — works correctly but does not scale to millions of
  rows without additional PG full-text indexes.
- No `search` parameter on the public hero video endpoint or comments endpoint.
- Tag-join search uses `DISTINCT` to avoid duplicates — correct, but adds a
  sort step.

---

### Cache Candidates

No caching layer exists. Safe future candidates:

| Endpoint | Rationale |
|---|---|
| `GET /api/public/hero-video/` | Single read-heavy endpoint; invalidate on video publish/update |
| `GET /api/gallery/albums/` | List changes rarely; invalidate on album publish/update |
| `GET /api/gallery/field-notes/` | Changes rarely |

Do not cache:
- Admin endpoints
- `/api/public/messages/` (write)
- Upload / status refresh responses
- Auth / session responses

---

### API Response Size Risk

| Endpoint | Risk | Specific fields |
|---|---|---|
| `GET /api/gallery/videos/` | High | `description_bs`, `description_en` in every video card |
| `GET /api/gallery/albums/<slug>/media/` | Medium | Full media list unpaginated; `description` in each item |
| `GET /api/gallery/admin/videos/` | Medium | `description_bs`, `description_en`; tags N+1 |
| `GET /api/gallery/admin/image-galleries/` | Low | `description_bs/en`, `seo_*` fields returned in list |

---

### Delete, Hide, and Archive Behavior

- **Unpublish (albums):** `PATCH /api/gallery/albums/<slug>/` with `is_published=false` (staff only). Supported. ✅
- **Hide video (set `is_public=false`):** `PATCH /api/gallery/admin/videos/<pk>/` with `is_published=false` (maps to `is_public`). Supported. ✅
- **Delete video record:** `DELETE /api/gallery/admin/videos/<pk>/`. Removes Django record only. **Cloudflare Stream asset is NOT deleted** (documented in view docstring). ❌ Orphaned Cloudflare assets accumulate.
- **Archive:** No `archived` status or field on `VideoClip` or `Album`. Only `VisitorMessage` has an `archived` status.
- **Failed upload cleanup:** No automation. Failed video records remain in DB with `is_public=True`, `status='failed'`.
- **Deleted MediaItem:** Removing a `MediaItem` does not call Cloudflare Images API or delete local files. Orphaned assets accumulate.

---

## Missing Scalability Pieces

1. **No pagination class** — all list endpoints unbounded.
2. **No dedicated public video list endpoint** — `GET /api/gallery/videos/` is dual public/admin.
3. **`VideoClipSerializer` used for public list and detail** — sends descriptions in list.
4. **Missing composite index `(is_public, status)` on `VideoClip`** — most-queried combination has no index.
5. **Missing index `(is_public, status, created_at)` on `VideoClip`** — needed for cursor pagination.
6. **Missing `is_published` index on `Album`** — every public album query scans full table.
7. **`select_related('cover_media')` missing** on `AlbumListCreateView` and `AlbumRetrieveUpdateDestroyView`.
8. **`prefetch_related('tags')` missing** on `AlbumRetrieveUpdateDestroyView`, `AdminVideoItemListView`.
9. **`select_related('album')` missing** on `AlbumMediaListCreateView`.
10. **No `published_at` on `VideoClip`** — impossible to sort/filter by publish date.
11. **No `published_at` on `Album`** — same issue.
12. **No custom manager for `public_ready()`** — filter logic duplicated in 3 views.
13. **No populated-albums query** — frontend receives empty published albums.
14. **`VideoClipSerializer` lacks `?lang=` support** — inconsistent with album/field-note serializers.

---

## Recommended Backend Architecture

### Pagination

- **Public list endpoints:** DRF `CursorPagination` with `ordering='-created_at'`.
  Cursor pagination is stable under concurrent inserts and avoids `OFFSET`
  performance degradation.
- **Admin list endpoints:** DRF `PageNumberPagination` — simpler for admin
  UIs that need "jump to page N".
- **Default page size:** 12 for public (card grid), 50 for admin.

Set in `config/settings.py`:
```python
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': None,  # per-view only
    'PAGE_SIZE': 12,
}
```
Apply `CursorPagination` per-view to avoid accidentally paginating endpoints
that should not be paginated (e.g., single-item lookups, write endpoints).

---

### Recommended Serializers

```
PublicVideoCardSerializer
  id, title (lang-resolved), album_id, album_title (lang-resolved),
  cloudflare_uid, cloudflare_thumbnail_url, duration_seconds, created_at

PublicVideoDetailSerializer (extends card fields)
  + description (lang-resolved), cloudflare_playback_url, tags (nested)

PublicAlbumCardSerializer  ≈ current AlbumListSerializer (fix select_related)
PublicAlbumDetailSerializer  ≈ current AlbumDetailSerializer (fix select_related + prefetch)

AdminVideoItemSerializer  — keep as-is (already separate)
VideoClipSerializer  — rename or scope to upload/sync responses only
```

---

### Recommended Endpoint Split

```
Public endpoints — /api/public/
  GET /api/public/videos/          — paginated card list (new endpoint)
  GET /api/public/videos/<pk>/     — video detail (new endpoint)
  GET /api/public/albums/          — paginated album card list (new endpoint)
  GET /api/public/albums/<slug>/   — album detail (new endpoint)
  GET /api/public/hero-video/      — keep as-is
  POST /api/public/messages/       — keep as-is
  GET /api/public/videos/<pk>/comments/  — keep, add pagination

Legacy gallery endpoints — keep for backwards compatibility during transition
  GET /api/gallery/videos/         — keep working, deprecate later
  GET /api/gallery/albums/         — keep working, deprecate later
```

---

### Recommended Database Indexes

Priority order:

```python
# VideoClip — critical for public browse
models.Index(fields=['is_public', 'status']),
models.Index(fields=['is_public', 'status', 'created_at']),

# Album — critical for public browse
models.Index(fields=['is_published']),
models.Index(fields=['is_published', 'gallery_type']),
models.Index(fields=['is_published', 'display_order']),

# MediaItem — for album media lists
models.Index(fields=['album', 'is_published']),

# FieldNote — for public list
models.Index(fields=['is_published']),
models.Index(fields=['is_published', 'published_at']),
```

---

### Recommended Query Optimizations

| View | Fix |
|---|---|
| `AlbumListCreateView` | Add `.select_related('cover_media')` |
| `AlbumRetrieveUpdateDestroyView` | Add `.select_related('cover_media').prefetch_related('tags')` |
| `AlbumMediaListCreateView` | Add `.select_related('album')` |
| `FieldNoteListView` | Add `.select_related('cover_image')` |
| `FieldNoteDetailView` | Add `.select_related('cover_image')` |
| `AdminVideoItemListView` | Add `.prefetch_related('tags')` |
| Public video detail view (new) | Add `.select_related('album').prefetch_related('tags')` |

---

### Recommended Media Provider Responsibilities

| Provider | Responsibility |
|---|---|
| **Cloudflare Stream** | Store and stream video bytes; provide playback URL and thumbnail URL |
| **Cloudflare Images** | Store and deliver image bytes; provide `public_url` and `thumbnail_url` |
| **Django database** | Canonical source of truth for all metadata, ordering, visibility, status, titles, tags |
| **Backend API** | Returns stored URLs — never calls Cloudflare at public request time |
| **Frontend** | Consumes paginated backend API only; does not filter locally |

---

### Recommended Frontend/Backend Contract

```
GET /api/public/videos/?cursor=&page_size=12&album=<pk>&tag=<slug>&search=&lang=bs

Response:
{
  "next": "...",
  "previous": "...",
  "results": [
    {
      "id": 1,
      "title": "Orlovi u planini",
      "album_id": 3,
      "album_title": "Plješevica",
      "cloudflare_uid": "...",
      "cloudflare_thumbnail_url": "...",
      "duration_seconds": 120,
      "created_at": "2026-06-01T10:00:00Z"
    },
    ...
  ]
}
```

---

## Recommended Implementation Phases

### Phase 1 — Paginated public video endpoint

- Add `REST_FRAMEWORK` settings block with no default pagination class
- Add `PublicVideoCardSerializer` (no descriptions, lang-resolved title, album title via `select_related`)
- Add `PublicVideoDetailSerializer`
- Add `GET /api/public/videos/` with `CursorPagination`, `?album`, `?tag`, `?search`, `?lang` filters
- Add `GET /api/public/videos/<pk>/` detail endpoint
- Tests for both endpoints
- **Scope:** `config/settings.py`, `gallery/serializers.py`, `gallery/views.py`, `gallery/public_urls.py`, `gallery/tests.py`

### Phase 2 — Query optimization and critical indexes

- Add composite index `(is_public, status)` and `(is_public, status, created_at)` on `VideoClip`
- Add index `is_published` on `Album`
- Add `select_related('cover_media')` to `AlbumListCreateView` and `AlbumRetrieveUpdateDestroyView`
- Add `prefetch_related('tags')` to `AlbumRetrieveUpdateDestroyView`
- Add `select_related('album')` to `AlbumMediaListCreateView`
- Add `select_related('cover_image')` to `FieldNoteListView` and `FieldNoteDetailView`
- Add `prefetch_related('tags')` to `AdminVideoItemListView`
- Tests to confirm no regressions
- **Scope:** `gallery/models.py`, migration, `gallery/views.py`

### Phase 3 — Paginated public album endpoints

- Add `GET /api/public/albums/` with cursor or page-number pagination
- Add `GET /api/public/albums/<slug>/` detail with paginated media items
- Populated-albums annotation query
- Admin pagination (page-number) on `admin/videos/`, `admin/images/`, etc.
- **Scope:** `gallery/views.py`, `gallery/public_urls.py`, `gallery/tests.py`

### Phase 4 — Optional: caching and polish

- Cache `hero-video` response (short TTL)
- Add `published_at` to `VideoClip` and `Album`
- Webhook or polling mechanism for Cloudflare status updates
- Auto-set `is_public=False` on `status='failed'`

---

## Files Inspected

| File | Purpose |
|---|---|
| `gallery/models.py` | All models |
| `gallery/serializers.py` | All serializers |
| `gallery/views.py` | All views |
| `gallery/urls.py` | Admin + legacy public URL routing |
| `gallery/public_urls.py` | Public URL routing |
| `config/settings.py` | DRF settings, email, DB, Cloudflare settings |
| `config/urls.py` | Root URL configuration |
| `gallery/migrations/0001_initial.py` | Initial schema |
| `gallery/migrations/0008_videoclip.py` | VideoClip creation |
| `gallery/migrations/0009_album_gallery_type.py` | gallery_type field |
| `gallery/migrations/0010_tags_and_m2m.py` | Tag model + M2M |
| `gallery/migrations/0011_visitor_message.py` | VisitorMessage creation |
| `gallery/migrations/0012_visitor_message_video_context.py` | VisitorMessage indexes |
| `gallery/migrations/0013_video_timestamp_comment.py` | VideoTimestampComment + indexes |
| `gallery/migrations/0014_visitor_message_replied_at_reply_model.py` | replied_at + VisitorMessageReply |
| `gallery/services/cloudflare_stream.py` | Stream upload/sync service |
| `gallery/services/cloudflare_images.py` | Images upload service |

---

## Validation

Safe inspection only. No code was modified.

```
python manage.py check
```
```
System check identified no issues (0 silenced).
```

Tests were run (126/126 pass) in the previous session to confirm baseline.
No additional test run performed for this audit.

---

## No-Code-Change Confirmation

No source files were modified during this audit.
No migrations were created or run.
No tests were modified.
All findings are derived from reading the actual source files listed above.
