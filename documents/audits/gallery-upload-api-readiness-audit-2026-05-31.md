# Gallery Upload API Readiness Audit

**Date:** 2026-05-31  
**Repository:** `kata-photos-backend`  
**Scope:** Audit only — no code changes made  
**Auditor:** GitHub Copilot (Claude Sonnet 4.6)

---

## Files Inspected

| File | Purpose |
|---|---|
| `gallery/models.py` | Album, MediaItem, FieldNote model definitions |
| `gallery/serializers.py` | Public read serializers |
| `gallery/views.py` | API view classes |
| `gallery/urls.py` | URL routing |
| `gallery/admin.py` | Django admin registration |
| `gallery/migrations/0001_initial.py` | Initial schema |
| `gallery/migrations/0002_alter_mediaitem_original_file.py` | `upload_to` path correction |
| `gallery/migrations/0003_bilingual_fields.py` | Added `_en`/`_bs` fields |
| `gallery/migrations/0004_copy_content_to_en_fields.py` | Data migration — copied legacy fields to `_en` |
| `gallery/migrations/0005_alter_album_options_fieldnote.py` | Added FieldNote model |
| `config/settings.py` | Django settings |
| `config/urls.py` | Root URL configuration |
| `requirements.txt` | Installed packages |

---

## 1. Current Model Structure

### Album

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | Auto |
| `slug` | SlugField | unique | Required at DB level |
| `title` | CharField(200) | no blank | Legacy base field — still required |
| `title_en` | CharField(200) | blank=True | Bilingual |
| `title_bs` | CharField(200) | blank=True | Bilingual |
| `description` | TextField | blank=True | Legacy base field |
| `description_en` | TextField | blank=True | Bilingual |
| `description_bs` | TextField | blank=True | Bilingual |
| `seo_title` | CharField(200) | blank=True | Legacy SEO |
| `seo_title_en` | CharField(200) | blank=True | Bilingual |
| `seo_title_bs` | CharField(200) | blank=True | Bilingual |
| `seo_description` | TextField | blank=True | Legacy SEO |
| `seo_description_en` | TextField | blank=True | Bilingual |
| `seo_description_bs` | TextField | blank=True | Bilingual |
| `cover_media` | ForeignKey → MediaItem | null, blank, SET_NULL | Optional |
| `is_published` | BooleanField | default=False | Controls public visibility |
| `display_order` | PositiveIntegerField | default=0 | Sort order |
| `created_at` | DateTimeField | auto_now_add | Auto |
| `updated_at` | DateTimeField | auto_now | Auto |

**Ordering:** `['display_order', 'title_en', 'title']`

**Notable:** The legacy `title` field has no `blank=True`, making it a required field at the model/form level. The bilingual `title_en` and `title_bs` are both optional. This is inconsistent with a Bosnian-first policy.

### MediaItem

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | Auto |
| `album` | ForeignKey → Album | CASCADE | Required |
| `media_type` | CharField(10) | choices: image/video, default='image' | |
| `title` | CharField(200) | blank=True | Legacy |
| `title_en` | CharField(200) | blank=True | Bilingual |
| `title_bs` | CharField(200) | blank=True | Bilingual |
| `description` | TextField | blank=True | Legacy |
| `description_en` | TextField | blank=True | Bilingual |
| `description_bs` | TextField | blank=True | Bilingual |
| `alt_text` | CharField(500) | blank=True | Legacy |
| `alt_text_en` | CharField(500) | blank=True | Bilingual |
| `alt_text_bs` | CharField(500) | blank=True | Bilingual |
| `caption` | CharField(500) | blank=True | Legacy |
| `caption_en` | CharField(500) | blank=True | Bilingual |
| `caption_bs` | CharField(500) | blank=True | Bilingual |
| `tags` | JSONField | blank=True, default=list | |
| `is_published` | BooleanField | default=False | Controls public visibility |
| `display_order` | PositiveIntegerField | default=0 | Sort order |
| `provider` | CharField(20) | choices: local/cloudinary/cloudflare_stream, default='local' | |
| `provider_public_id` | CharField(500) | blank=True | For external CDN IDs |
| `original_file` | FileField | upload_to='gallery/originals/', null, blank | Local file upload |
| `public_url` | URLField(1000) | blank=True | External provider URL |
| `thumbnail_url` | URLField(1000) | blank=True | External provider thumbnail |
| `width` | PositiveIntegerField | null, blank | Manual entry only |
| `height` | PositiveIntegerField | null, blank | Manual entry only |
| `duration_seconds` | FloatField | null, blank | Video only |
| `file_size` | PositiveIntegerField | null, blank | Manual entry only |
| `created_at` | DateTimeField | auto_now_add | Auto |
| `updated_at` | DateTimeField | auto_now | Auto |

**Ordering:** `['display_order', 'id']`

---

## 2. Current Upload / Storage Behavior

### File upload field

`MediaItem.original_file` is a `FileField` (not `ImageField`).

- **Accepts:** any file type — no format validation
- **Stores to:** `MEDIA_ROOT/gallery/originals/` (path set in migration 0002)
- `MEDIA_ROOT` = `BASE_DIR / "media"` → `c:\Users\nlekk\kata-photos-backend\media\`
- `MEDIA_URL` = `"/media/"` (configurable via env)

### Width / height

`width` and `height` are plain `PositiveIntegerField` with no auto-population. They must be set manually. There is no `Pillow` or image-processing step triggered on save.

### Thumbnails

No thumbnail generation exists. `thumbnail_url` is a plain URLField. For `provider='local'`, the serializer falls back to serving `original_file.url` as the thumbnail URL. There is no separate thumbnail file created.

### Local media serving in development

`config/urls.py` adds `static(MEDIA_URL, document_root=MEDIA_ROOT)` when `DEBUG=True`. Uploaded files are therefore accessible at `http://localhost:8000/media/gallery/originals/<filename>` in development.

### External providers

`provider` supports `cloudinary` and `cloudflare_stream` as choice values, but:
- Neither `cloudinary` nor `cloudflare-storage` packages are in `requirements.txt`
- No provider-specific upload logic exists in models or views
- External providers are placeholder architecture only — not implemented

### Summary

| Question | Answer |
|---|---|
| Can the backend accept uploaded image files? | **Yes** — via `original_file` FileField in Django admin and (in principle) via multipart form POST |
| Is there an ImageField? | **No** — plain `FileField`, no image validation |
| Does the model store only URLs? | **No** — `original_file` FileField exists alongside `public_url`/`thumbnail_url` |
| Width/height auto-generated? | **No** — manual only |
| Thumbnails auto-generated? | **No** — `thumbnail_url` is a URLField; local provider returns original file URL as thumbnail |
| Storage type? | Local (`MEDIA_ROOT`) for `provider='local'` |
| Django serves uploaded media in development? | **Yes** — `DEBUG=True` enables `static()` media serving |

---

## 3. Current Admin Capabilities

### AlbumAdmin

- `list_display`: `title_en`, `slug`, `is_published`, `display_order`, `created_at`
- `list_filter`: `is_published`
- `search_fields`: `title_en`, `slug`
- `readonly_fields`: `created_at`, `updated_at`
- Fieldsets: Publishing/Ordering | English Content | Bosnian Content | SEO English | SEO Bosnian | Timestamps
- **No `prepopulated_fields` for `slug`** — must be typed manually
- Albums can be created and saved through admin

### MediaItemAdmin

- `list_display`: `id`, `title_en`, `album`, `media_type`, `provider`, `is_published`, `display_order`
- `list_filter`: `is_published`, `media_type`, `provider`
- `search_fields`: `title_en`, `alt_text_en`, `provider_public_id`
- `readonly_fields`: `created_at`, `updated_at`
- Fieldsets: Album/Publishing/Ordering | English Content | Bosnian Content | Media/Provider | Metadata | Timestamps
- `original_file` is exposed in the Media/Provider fieldset — file upload works in admin now

### FieldNoteAdmin

- `prepopulated_fields`: `{'slug': ('title_en',)}` — slug auto-fills from English title
- All bilingual fields exposed
- `is_published` validated in `FieldNote.clean()` (requires `title_en` and `body_en` before publishing)

### Admin gaps

- `AlbumAdmin` lacks `prepopulated_fields` for `slug`
- `AlbumAdmin` has no `clean()` validation for Bosnian-first rules
- `MediaItemAdmin` has no file type validation on `original_file`
- `MediaItemAdmin` has no auto-population of `width`, `height`, or `file_size` on save
- No custom admin action for bulk publishing or translation

---

## 4. Current API Endpoints

### Registered URLs

Base prefix: `/api/gallery/` (from `config/urls.py` → `include("gallery.urls")`)

| Method | URL | View | Queryset filter |
|---|---|---|---|
| GET | `/api/gallery/albums/` | `AlbumListView` | `is_published=True` |
| GET | `/api/gallery/albums/<slug>/` | `AlbumDetailView` | `is_published=True` |
| GET | `/api/gallery/albums/<slug>/media/` | `AlbumMediaListView` | album `is_published=True` + items `is_published=True` |
| GET | `/api/gallery/media/<pk>/` | `MediaItemDetailView` | item `is_published=True` + album `is_published=True` |
| GET | `/api/gallery/field-notes/` | `FieldNoteListView` | `is_published=True` |
| GET | `/api/gallery/field-notes/<slug>/` | `FieldNoteDetailView` | `is_published=True` |

### Language parameter

All views inherit `LangContextMixin`. A `?lang=bs` or `?lang=en` query parameter sets the language context. Defaults to `en`. Only `en` and `bs` are accepted; any other value falls back to `en`.

### Write endpoints

**None exist.** There are no `POST`, `PUT`, `PATCH`, or `DELETE` endpoints. The entire API is read-only.

### What is returned by the public serializers

**AlbumListSerializer** fields: `id`, `slug`, `title` (translated), `description` (translated), `display_order`, `cover` (nested: `id`, `thumbnail_url`, `alt_text`)

**AlbumDetailSerializer** fields: `id`, `slug`, `title`, `description`, `seo_title`, `seo_description`, `display_order`, `cover`, `created_at`

**MediaItemPublicSerializer** fields: `id`, `album_slug`, `media_type`, `title`, `description`, `alt_text`, `caption`, `tags`, `public_url`, `thumbnail_url`, `width`, `height`, `display_order`

**Note:** `is_published`, `updated_at`, `provider`, `original_file` path, `file_size`, `duration_seconds`, `provider_public_id` are not exposed in public API responses.

---

## 5. Current Permission / Auth Behavior

### DRF configuration

No `REST_FRAMEWORK` settings dict exists in `config/settings.py`. DRF defaults apply:

| Setting | Default value |
|---|---|
| `DEFAULT_AUTHENTICATION_CLASSES` | `SessionAuthentication`, `BasicAuthentication` |
| `DEFAULT_PERMISSION_CLASSES` | `AllowAny` |
| `DEFAULT_PARSER_CLASSES` | `JSONParser`, `FormParser`, `MultiPartParser` |

### Effective behavior

- All current API views are **publicly accessible** — no authentication required
- No JWT or token auth is installed (`djangorestframework-simplejwt` is not in `requirements.txt`)
- CSRF middleware (`CsrfViewMiddleware`) is active in `MIDDLEWARE` — relevant for session-authenticated write requests from a browser frontend
- Django admin uses session authentication — admin login works

### What is missing

- No write endpoints exist yet, so permission enforcement has not been needed
- No `IsAdminUser` or `IsAuthenticated` permission class is applied anywhere
- No token/JWT authentication installed
- No per-view permission overrides

### Recommended first safe rule

When write endpoints are added:

```
Only authenticated staff/admin users (is_staff=True) can create, update, or delete albums and media items.
Public unauthenticated users can only read published content.
```

This can be enforced via DRF `IsAdminUser` permission class (requires `is_staff=True`) on write views, with `AllowAny` or `IsAuthenticatedOrReadOnly` on read views.

For session-based upload from the frontend, CSRF tokens must be handled. For a stateless API upload flow (e.g. Vite/React frontend), `TokenAuthentication` or `simplejwt` would be preferable to avoid CSRF complexity.

---

## 6. Bosnian-First Content Readiness

### Current state

All bilingual content fields (`title_bs`, `description_bs`, `alt_text_bs`, `caption_bs`, and their `_en` counterparts) are `blank=True` at the model level. **No field is required in any language.**

The legacy `Album.title` field (no `blank=True`) is still present and still required. This is an inconsistency — a new album will fail validation if `title` is empty, even if `title_bs` is populated.

### Serializer fallback logic

```python
def resolve_translated(obj, field_name, lang):
    value = getattr(obj, f"{field_name}_{lang}", "")
    fallback = getattr(obj, f"{field_name}_en", "")
    return value or fallback
```

- If `lang=bs` and `title_bs` is empty → falls back to `title_en`
- If `lang=en` and `title_en` is empty → `title_en` is also the fallback, returns `""`
- There is **no fallback from `_en` to `_bs`**

This means `title_en` is the effective content fallback for all languages, which contradicts a Bosnian-first policy.

### What is missing for Bosnian-first

1. `title_bs` should be required (no `blank=True`) for both Album and MediaItem — or at minimum required before `is_published=True`
2. The serializer fallback chain should be: `_bs` → `_en` when `lang=bs` AND `_en` → `_bs` when `lang=en` and `_en` is empty (or simply serve Bosnian as the canonical source)
3. The legacy `Album.title` field and its usage in `__str__` and `ordering` should be evaluated for deprecation
4. `alt_text_bs` is the most important accessibility field for the photographer's content — should be recommended for images

### FieldNote comparison

`FieldNote.clean()` enforces `title_en` and `body_en` before publishing — this is an English-first validation pattern and should be reconsidered for a Bosnian-first site.

---

## 7. Missing Pieces for Upload

| Missing piece | Detail |
|---|---|
| Album creation API | No `POST /api/gallery/albums/` endpoint |
| Media upload API | No `POST /api/gallery/albums/<slug>/media/` endpoint |
| Write serializers | No serializer for accepting Album or MediaItem input |
| Permission enforcement | No auth or permission class applied to any view |
| Token/JWT auth | Not installed; needed for stateless upload from frontend |
| `ImageField` or file validation | `FileField` accepts any file type — no image validation |
| Auto-populate width/height | Not implemented; `Pillow` not in requirements |
| Thumbnail generation | Not implemented; local provider returns original as thumbnail |
| Slug auto-generation for albums | Admin does not have `prepopulated_fields`; no API-side slug generation |
| Bosnian-first enforcement | No model-level validation for `title_bs` being present |
| File size / dimension population on save | No `save()` override or signal to capture these values |
| CORS config for multipart POST | CORS is configured for GET; multipart POST from frontend not yet tested |

---

## 8. Risks and Edge Cases

| Risk | Notes |
|---|---|
| **Large image files** | No `FILE_UPLOAD_MAX_MEMORY_SIZE` or content-length validation configured. Django default is 2.5 MB in-memory. |
| **Invalid file types** | `FileField` (not `ImageField`) — any file accepted. SVG, executables, etc. could be uploaded. |
| **Missing alt text** | `alt_text_bs` is blank=True — no enforcement. Accessibility risk. |
| **Empty album** | Albums can be published with no media items — no validation against this. |
| **Duplicate slug** | `slug` is `unique=True` — duplicate slug will raise DB IntegrityError. No user-friendly handling at API layer yet. |
| **Deleting album with media** | `MediaItem` FK to Album is `CASCADE` — deleting an album deletes all its media items. No soft-delete or confirmation mechanism. |
| **Cover image selection** | `cover_media` FK uses `SET_NULL` on delete — cover clears safely. But no API mechanism to set cover. Admin only. |
| **Thumbnail generation** | No thumbnail generated — original file served as thumbnail. Large originals will be sent to client. |
| **Storage path cleanup** | `FileField` does not delete the physical file when a record is deleted. Old files accumulate in `media/gallery/originals/`. |
| **Local vs production storage** | Local `FileField` paths will break in production if storage backend changes. `MEDIA_ROOT` paths are not portable to S3/Cloudinary. |
| **Cloudinary/Cloudflare future migration** | Provider choice field exists but no integration code. A storage abstraction layer will be needed before migrating. |
| **Frontend upload progress** | Not relevant at backend level yet, but multipart streaming and response format should be planned. |
| **CSRF for session-based upload** | `CsrfViewMiddleware` is active. A browser-based POST from the frontend will require a valid CSRF token unless using token auth with `csrf_exempt`. |
| **Public API exposing unpublished uploads** | Current public views filter `is_published=True` — new uploads start unpublished. Safe by default. |
| **Legacy `title` field on Album** | Still required (no blank=True), which conflicts with Bosnian-first input. Needs migration to make blank. |
| **Pillow not installed** | `width`/`height` cannot be auto-populated without Pillow. DRF `ImageField` also requires Pillow. |

---

## 9. Recommended Implementation Phases

### Phase 1 — Django Admin Bosnian-first fix

**Goal:** Ensure albums and media can be created through admin with Bosnian content as the primary content source.

Minimum changes:
- Add `prepopulated_fields = {'slug': ('title_bs',)}` to `AlbumAdmin` (or allow manual slug with Bosnian title as hint)
- Make `Album.title` `blank=True` (and add a migration) to remove the English-title-as-required inconsistency
- Add a `clean()` method to `Album` that requires `title_bs` when `is_published=True`
- Optionally: recommend `alt_text_bs` via admin help text

### Phase 2 — Image file upload storage

**Goal:** Confirm that local `FileField` upload works end-to-end and optionally switch to `ImageField`.

Minimum changes:
- Install `Pillow`
- Change `original_file` from `FileField` to `ImageField` to get image format validation and optionally auto-populate `width`/`height`
- Override `MediaItem.save()` to populate `width`, `height`, and `file_size` from the uploaded file when `provider='local'`
- Validate that `MEDIA_ROOT` and `MEDIA_URL` work correctly with `DEBUG=True`

### Phase 3 — Protected album creation endpoint

**Goal:** Allow the authenticated admin/staff user to create albums via API.

Minimum changes:
- Install `djangorestframework-simplejwt` or decide on session+CSRF auth strategy
- Add `AlbumWriteSerializer` accepting: `title_bs` (required), `slug` (optional, auto-generate from `title_bs`), `description_bs`, `title_en`, `description_en`, `display_order`
- Add `POST /api/gallery/albums/` view with `IsAdminUser` permission
- Add `PATCH /api/gallery/albums/<slug>/` and `DELETE /api/gallery/albums/<slug>/` with same permission

### Phase 4 — Protected media upload endpoint

**Goal:** Allow the admin to upload an image file to an album via API.

Minimum changes:
- Add `MediaItemWriteSerializer` accepting multipart data: `file` (image), `title_bs`, `caption_bs`, `alt_text_bs` (recommended required for publishing), `title_en`, `caption_en`, `alt_text_en`, `display_order`
- Add `POST /api/gallery/albums/<slug>/media/` write view with `IsAdminUser` permission
- Add `PATCH /api/gallery/media/<pk>/` and `DELETE /api/gallery/media/<pk>/` with same permission
- Ensure `is_published=False` on newly uploaded items by default

### Phase 5 — Return uploaded media through public API

**Goal:** Verify the existing public endpoints correctly serve newly uploaded and published media.

Minimum changes:
- Test that `GET /api/gallery/albums/<slug>/media/` returns items with `is_published=True`
- Test that `public_url` and `thumbnail_url` resolve correctly for `provider='local'` items
- Confirm `width`, `height` are populated and returned

### Phase 6 — Frontend upload UI (future, out of scope)

Frontend to be built separately. Backend API contract from Phase 3 and Phase 4 defines the interface.

---

## 10. Recommended First Implementation Prompt

> **Prompt for next coding session:**
>
> In `kata-photos-backend`, implement Phase 1 and Phase 2 of the gallery upload readiness plan:
>
> **Phase 1 — Admin Bosnian-first fix:**
> - Make `Album.title` `blank=True` in the model and add a migration
> - Add `AlbumAdmin.prepopulated_fields = {'slug': ('title_bs',)}`
> - Add `Album.clean()` requiring `title_bs` when `is_published=True`
>
> **Phase 2 — Image upload storage:**
> - Add `Pillow` to `requirements.txt`
> - Change `MediaItem.original_file` from `FileField` to `ImageField`
> - Add a migration for the field change
> - Override `MediaItem.save()` to auto-populate `width`, `height`, and `file_size` from the uploaded file when `provider='local'` and `original_file` is set
>
> No API write endpoints yet. No serializer changes. Admin only.
> Bosnian-first: do not add fake English content or auto-translations.

---

## 11. Commands Run

```
Get-Content c:\Users\nlekk\kata-photos-backend\requirements.txt
New-Item -ItemType Directory -Force -Path "c:\Users\nlekk\kata-photos-backend\documents\audits"
```

Files were read using the VS Code file-reading tools (no shell `cat` or `grep` commands used for source inspection).

---

## 12. Validation Performed

- All source files read directly from disk — no README or comment-based assumptions made
- Migration chain traced: 0001 → 0002 → 0003 → 0004 → 0005
- `upload_to` path discrepancy between 0001 (`media/originals/`) and 0002 (`gallery/originals/`) confirmed — 0002 corrects it, current model and migration 0002 agree
- `requirements.txt` confirmed: no Pillow, no JWT, no Cloudinary package installed
- `REST_FRAMEWORK` settings block confirmed absent from `config/settings.py`
- All six URL patterns confirmed against view class signatures

---

## 13. Confirmations

- **No frontend files were touched.** This repository contains only the Django backend.
- **No code changes were made.** This is an audit report only.
- **No README or comment content was used as a source of truth.** All findings are derived from actual Python source files and migration files.
