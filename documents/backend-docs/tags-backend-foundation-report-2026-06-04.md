# Tags Backend Foundation Report — 2026-06-04

## Summary

A reusable `Tag` model has been added to the gallery app. Tags can be assigned to `Album` and `VideoClip` records via ManyToMany relationships. Admin-only CRUD endpoints are provided for tag management. Public album and video list responses now include tags. Public list endpoints support `?tag=<slug>` and `?search=<query>` filtering. All 70 tests pass.

---

## Files Changed

| File | Type of Change |
|------|---------------|
| `gallery/models.py` | Added `Tag` model; added `tags` M2M field to `Album` and `VideoClip` |
| `gallery/admin.py` | Registered `TagAdmin`; added `filter_horizontal = ('tags',)` and Tags fieldset to `AlbumAdmin` and `VideoClipAdmin` |
| `gallery/serializers.py` | Added `TagSerializer`, `TagWriteSerializer`, `_TagsM2MMixin`; added `tags` to public and admin read/write serializers for `Album` and `VideoClip` |
| `gallery/views.py` | Added `AdminTagListCreateView`, `AdminTagRetrieveUpdateDestroyView`; updated `AlbumListCreateView` and `VideoClipListView` for `?tag=` and `?search=` filtering |
| `gallery/urls.py` | Added `admin/tags/` and `admin/tags/<pk>/` routes |
| `gallery/tests.py` | Added `Tag` import; added 28 new tests across 5 test classes |
| `gallery/migrations/0010_tags_and_m2m.py` | New migration: `Tag` model + M2M fields on `Album` and `VideoClip` |

Total: 7 files (1 new migration, 6 modified).

---

## Models Added/Changed

### New model: `Tag`

```python
class Tag(models.Model):
    name_bs   = CharField(max_length=100)            # required
    name_en   = CharField(max_length=100, blank=True) # optional
    slug      = SlugField(max_length=120, unique=True) # auto-generated from name_bs
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    # Meta.ordering = ['slug']
```

`save()` auto-generates `slug` from `name_bs` if not supplied.

### Modified: `Album`

Added:

```python
tags = ManyToManyField('Tag', blank=True, related_name='albums')
```

### Modified: `VideoClip`

Added:

```python
tags = ManyToManyField('Tag', blank=True, related_name='video_clips')
```

---

## Migrations Created

| Migration | Description |
|-----------|-------------|
| `gallery/migrations/0010_tags_and_m2m.py` | Creates `gallery_tag` table; creates `gallery_album_tags` and `gallery_videoclip_tags` join tables |

Applied with `python manage.py migrate`. No data-destructive changes.

---

## API Endpoints Added/Changed

### New admin endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/gallery/admin/tags/` | List all tags |
| `POST` | `/api/gallery/admin/tags/` | Create a tag |
| `GET` | `/api/gallery/admin/tags/<pk>/` | Retrieve a tag |
| `PATCH` | `/api/gallery/admin/tags/<pk>/` | Update a tag |
| `DELETE` | `/api/gallery/admin/tags/<pk>/` | Delete a tag |

### Modified public endpoints

| Endpoint | Change |
|----------|--------|
| `GET /api/gallery/albums/` | Response now includes `tags` array; supports `?tag=<slug>` and `?search=<query>` filters |
| `GET /api/gallery/albums/<slug>/` | Response now includes `tags` array |
| `GET /api/gallery/videos/` | Response now includes `tags` array; supports `?tag=<slug>` and `?search=<query>` filters |
| `GET /api/gallery/videos/<pk>/` | Response now includes `tags` array |

### Modified admin endpoints (no breaking changes)

All admin image gallery and video gallery read serializers now include `tags`. Write serializers for albums and videos now accept `tags` as a list of PKs.

### Tag response format (public)

```json
[
  {
    "id": 1,
    "name_bs": "Ptice",
    "name_en": "Birds",
    "slug": "ptice"
  }
]
```

### Filtering

```
GET /api/gallery/albums/?tag=ptice
GET /api/gallery/albums/?search=priroda
GET /api/gallery/videos/?tag=ptice
GET /api/gallery/videos/?search=orlovi
```

Search covers `title_bs`, `title_en`, `tags.name_bs`, `tags.name_en`. Queries use `.distinct()` to avoid duplicate results from join.

---

## Permission Behavior

| Action | Required permission |
|--------|-------------------|
| Create / update / delete tags | `IsAdminUser` (staff) |
| Attach tags to albums/videos | `IsAdminUser` (staff) |
| Read tags in public album/video responses | Public (`AllowAny`) |
| Filter by tag in public list | Public (`AllowAny`) |

No write endpoints are publicly accessible.

---

## Test Coverage Added

28 new tests across 5 test classes:

| Class | Tests | What is covered |
|-------|-------|----------------|
| `TagModelTests` | 4 | Model creation, slug auto-generation, uniqueness, optional name_en |
| `TagAdminAPITests` | 9 | Staff create/list/update/delete, non-staff/anon blocked, missing name_bs, duplicate slug, very long name |
| `TagAttachmentTests` | 6 | Attach on create/patch, clear tags, no-tag validity, delete-tag safety, VideoClip tags |
| `TagPublicResponseTests` | 3 | Tags in album list, empty tags list, tags in video list |
| `TagFilterTests` | 6 | Filter albums by tag, unknown tag returns empty, search albums by title, search by tag name, filter videos by tag, search videos by title |

All 42 existing tests continue to pass unchanged.

---

## Commands Run

```bash
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations gallery --name tags_and_m2m
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test gallery --verbosity=2
```

---

## Validation Results

```
manage.py check      → System check identified no issues (0 silenced)
manage.py test gallery → Ran 70 tests in 46.686s OK
```

All 70 tests pass (42 pre-existing + 28 new).

---

## Edge Cases Handled

| Edge case | How handled |
|-----------|-------------|
| Duplicate tag slug | Validated in `TagWriteSerializer.validate()`; returns HTTP 400 with `{'slug': '...'}` |
| Missing `name_bs` | `extra_kwargs = {'name_bs': {'required': True, 'allow_blank': False}}`; returns HTTP 400 |
| Missing `name_en` | Field is `blank=True`; empty string stored, no error |
| Deleting a tag attached to content | M2M `blank=True` — join rows deleted, album/video is unaffected (`test_deleting_tag_does_not_delete_album`) |
| Content with no tags | Valid; response includes `"tags": []` (`test_album_with_no_tags_is_valid`, `test_public_album_with_no_tags_returns_empty_list`) |
| Filtering by unknown tag | Returns empty list, no error (`test_filter_albums_by_unknown_tag_returns_empty`) |
| Very long tag names | `name_bs` max_length=100; exceeding it returns HTTP 400 (`test_very_long_name_bs_rejected`) |
| Slug conflicts on update | Excluded own PK before checking duplicates in `TagWriteSerializer.validate()` |
| Search with join duplicates | `.distinct()` applied when `?search=` is used |
| Patch with `tags=[]` | Clears all tags on the object (`test_patch_with_empty_tags_clears_tags`) |

---

## Confirmation: Frontend Files Not Touched

No frontend files were modified. Changes are limited to:
- `gallery/models.py`
- `gallery/admin.py`
- `gallery/serializers.py`
- `gallery/views.py`
- `gallery/urls.py`
- `gallery/tests.py`
- `gallery/migrations/0010_tags_and_m2m.py`

---

## Known Limitations / Next Steps

| Limitation | Notes |
|-----------|-------|
| No public `/api/public/tags/` listing endpoint | Not implemented; add if the frontend needs a standalone tag browser |
| No `?tags=` multi-tag AND/OR filtering | Current `?tag=` supports a single slug; multi-tag filtering can be added as a follow-up |
| `MediaItem.tags` is a JSONField (legacy) | Not migrated to the new `Tag` M2M in this phase; treat as a separate migration task |
| No `FieldNote` tags | Not in scope this phase; `FieldNote` has no existing tag field |
| No tag-level public listing endpoint | Can be added as `GET /api/public/tags/` when needed |
| No tag ordering by use count | Can be annotated in a future phase |
