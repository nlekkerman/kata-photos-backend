# Gallery Album Write API — Phase 3 Implementation Report

**Date:** 2026-06-01  
**Repository:** `kata-photos-backend`  
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)  
**Prerequisite:** Phase 1 & 2 — `documents/backend-docs/gallery-upload-phase-1-2-implementation-report-2026-06-01.md`

---

## Summary

Phase 3 adds protected album creation, update, and delete endpoints for staff/admin users. Public read endpoints are unchanged. No media upload endpoints were added. No frontend files were touched.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added `AlbumWriteSerializer` |
| `gallery/views.py` | Replaced `AlbumListView` with `AlbumListCreateView`; replaced `AlbumDetailView` with `AlbumRetrieveUpdateDestroyView` |
| `gallery/urls.py` | Updated imports to use new view names |
| `gallery/tests.py` | Replaced placeholder with 8 focused API tests |

**Total files changed: 4** (within the 1–5 target)  
**No migrations created.** Phase 3 is serializer/view-only — no model changes.

---

## Endpoints Added

| Method | URL | Auth required | Description |
|---|---|---|---|
| `POST` | `/api/gallery/albums/` | Staff/admin only | Create album |
| `PATCH` | `/api/gallery/albums/<slug>/` | Staff/admin only | Partial update album |
| `DELETE` | `/api/gallery/albums/<slug>/` | Staff/admin only | Delete album |

### Existing endpoints — unchanged behavior

| Method | URL | Auth | Description |
|---|---|---|---|
| `GET` | `/api/gallery/albums/` | Public | List published albums |
| `GET` | `/api/gallery/albums/<slug>/` | Public | Published album detail |
| `GET` | `/api/gallery/albums/<slug>/media/` | Public | Published media for album |
| `GET` | `/api/gallery/media/<pk>/` | Public | Published media item |

`PUT` is disabled on the detail endpoint (`http_method_names` excludes it). Only `PATCH` (partial update) is supported for write operations.

---

## Implementation Approach

### Combined views with per-method permissions

Rather than adding entirely separate URL entries (which cannot share a path in Django's URL routing), each album view was upgraded to a combined generic view with `get_permissions()` and `get_serializer_class()` overriding behavior per HTTP method:

```python
class AlbumListCreateView(LangContextMixin, generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AlbumWriteSerializer
        return AlbumListSerializer

    def get_queryset(self):
        if self.request.method == 'POST':
            return Album.objects.all()
        return Album.objects.filter(is_published=True)
```

Public GET behavior is identical to before. `LangContextMixin` is preserved for GET responses. Write serializers do not use `lang` context and are unaffected.

---

## Serializer: `AlbumWriteSerializer`

### Accepted input fields

| Field | Required | Notes |
|---|---|---|
| `title_bs` | Yes (on create) | Bosnian title — source of truth |
| `slug` | No | Auto-generated from `title_bs` if omitted on create |
| `description_bs` | No | |
| `seo_title_bs` | No | |
| `seo_description_bs` | No | |
| `title_en` | No | English optional |
| `description_en` | No | |
| `seo_title_en` | No | |
| `seo_description_en` | No | |
| `display_order` | No | |
| `is_published` | No | |

Read-only response fields: `id`, `created_at`, `updated_at`.

### Validation rules

1. **`title_bs` required on create** — enforced via `extra_kwargs {'required': True, 'allow_blank': False}`. For PATCH (partial=True), title_bs is optional if already set.

2. **Slug auto-generation** — if `slug` is absent on create, `slugify(title_bs)` is used. On PATCH, slug is not modified unless explicitly supplied.

3. **Duplicate slug** — checked in `validate()` with `Album.objects.filter(slug=slug)`. On update, the current instance is excluded. Returns `400 Bad Request` with `{'slug': '...'}` error — no raw `IntegrityError` leaks.

4. **Published requires title_bs** — if `is_published=True` and `title_bs` is empty (considering existing instance value on partial update), returns `400 Bad Request`.

### Fields intentionally excluded from write serializer

- `cover_media` — deferred to a later phase
- `original_file`, `public_url`, `thumbnail_url` — media upload deferred to Phase 4
- Legacy `title` field — not exposed; left untouched on existing records

---

## Permission Behavior

| User type | GET list/detail | POST create | PATCH update | DELETE |
|---|---|---|---|---|
| Anonymous | ✓ published only | 403 | 403 | 403 |
| Authenticated non-staff | ✓ published only | 403 | 403 | 403 |
| Staff / admin | ✓ published only | ✓ | ✓ all albums | ✓ all albums |

DRF's built-in `IsAdminUser` (`user.is_staff`) is used. No JWT or token auth was added. Existing session-based authentication (Django admin sessions) is used.

No global `REST_FRAMEWORK` settings were changed.

---

## Tests Added

File: `gallery/tests.py`  
Class: `AlbumWriteAPITests` (8 tests)

| Test | Assertion |
|---|---|
| `test_anonymous_cannot_create_album` | POST without auth → 401 or 403 |
| `test_non_staff_cannot_create_album` | POST as regular user → 401 or 403 |
| `test_staff_can_create_album_with_title_bs` | POST as staff → 201, album created |
| `test_staff_can_create_album_without_english_fields` | POST without `title_en` → 201, `title_en` is empty |
| `test_slug_auto_generates_from_title_bs` | POST without slug → slug = `slugify(title_bs)` |
| `test_duplicate_slug_returns_validation_error` | POST with duplicate slug → 400, `slug` in errors |
| `test_published_album_without_title_bs_rejected` | POST `is_published=True, title_bs=''` → 400 |
| `test_public_list_returns_only_published` | GET → only published albums visible |

---

## Commands Run and Results

```
python manage.py makemigrations --check --dry-run
```
→ `No changes detected` (exit 0). Phase 3 is serializer/view-only.

```
python manage.py migrate
```
→ `No migrations to apply.`

```
python manage.py check
```
→ `System check identified no issues (0 silenced).`

```
python manage.py test --verbosity=2
```
→ `Ran 8 tests in 7.834s OK` — all 8 tests passed.

---

## What Was Intentionally Not Changed

| Area | Reason |
|---|---|
| Media upload endpoints | Deferred to Phase 4 |
| `cover_media` write field | Deferred — not trivially safe without media item validation |
| `MediaItemAdmin` / `MediaItem` views | Out of scope |
| `FieldNote` views | Out of scope |
| JWT / token auth | Out of scope |
| Cloudinary / Cloudflare | Out of scope |
| Thumbnail generation | Out of scope |
| Django settings (`config/settings.py`) | No change needed |
| Global DRF permission defaults | Not changed |
| Public serializers (`AlbumListSerializer`, `AlbumDetailSerializer`) | Unchanged |

---

## Confirmation

- **No frontend files were touched.**
- **No media upload endpoint was added.**
- **No translation logic was added.**
- **No Cloudinary or Cloudflare logic was added.**
- **No thumbnail logic was added.**
- **No fake or dummy English content was generated.**
- **No broad refactor was performed.**
- **Existing public API behavior is stable and tested.**

---

## Risks and Follow-up Notes

1. **`IsAdminUser` requires `is_staff=True`.** Django admin users have this. Regular authenticated API consumers do not. If a future custom user role (e.g. photographer, editor) needs write access, a custom permission class will be needed.

2. **Session authentication only.** Staff users calling the API from outside the Django admin session (e.g. a future CMS frontend) will need CSRF tokens for unsafe methods (POST, PATCH, DELETE). Alternatively, adding `TokenAuthentication` or a session-based login endpoint will be required for that use case.

3. **Slug collision on auto-generation.** If two albums with the same `title_bs` are created, the second will fail with a `400 slug` error (no auto-append suffix). Staff must supply a unique slug manually in that case. This is intentional and explicit.

4. **Legacy `title` field.** Not exposed in `AlbumWriteSerializer`. Records created via the new API will have `title=''`. Any existing code reading `album.title` without fallback will return an empty string. `__str__` falls back correctly.

5. **PATCH allows updating `is_published`.** A staff user can publish an album via `PATCH /api/gallery/albums/<slug>/` with `{"is_published": true}`. The serializer validation will enforce `title_bs` must be set (either in the request or already on the instance). This is the intended behavior.

6. **Write queryset for PATCH/DELETE is `Album.objects.all()`.** Staff can update/delete unpublished albums. This is intentional — staff need to manage drafts.
