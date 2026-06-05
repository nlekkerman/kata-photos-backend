# Admin Image/Media Pagination Phase 4C Report

## Summary

Added page-number pagination and four database-level filters to the admin image
list endpoint. The endpoint is no longer unbounded. All changes are confined to
`gallery/views.py` and `gallery/tests.py`. No models, migrations, serializers,
public endpoints, or frontend files were changed.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/views.py` | Added `AdminImagePageNumberPagination`; replaced `AdminImageItemListCreateView.get_queryset` with filtered, ordered version; added `pagination_class` attribute; updated docstring |
| `gallery/tests.py` | Added 17 new tests in `AdminImageItemListAPITests` |

---

## Endpoint Updated

```
GET /api/gallery/admin/images/
```

Confirmed from `gallery/urls.py`:

```python
path('admin/images/', AdminImageItemListCreateView.as_view(), name='admin-image-list'),
```

The endpoint is registered under `/api/gallery/` (per `config/urls.py`), so the
full path is `/api/gallery/admin/images/`. Staff-only access is enforced by
`permission_classes = [IsAdminUser]` on the view.

POST (create/upload) behavior is unchanged — pagination only applies to GET.

---

## Pagination Behavior

| Parameter | Default | Max | Type |
|---|---|---|---|
| `page` | 1 | — | page number |
| `page_size` | 50 | 100 | integer |

Response shape (DRF `PageNumberPagination`):

```json
{
  "count": 1234,
  "next": "http://…/api/gallery/admin/images/?page=2",
  "previous": null,
  "results": []
}
```

Pagination class:

```python
class AdminImagePageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
```

This class is applied only to `AdminImageItemListCreateView` via
`pagination_class`. No global pagination was changed. `AdminVideoPageNumberPagination`
from Phase 4A is unchanged.

---

## Filters Implemented

All filters execute at the database level. No Python-level filtering is used.

### `?album=<pk>`

Filters by `album_id`. Legacy `?gallery=<pk>` parameter is also accepted for
backward compatibility with any existing admin clients using the old name.

### `?is_published=true|false`

Maps directly to the model field `MediaItem.is_published` (unlike VideoClip,
which uses `is_public` with an `is_published` alias in the serializer —
`MediaItem` uses `is_published` natively on the model).

Accepted truthy values: `true`, `1`. Accepted falsy values: `false`, `0`.
Any other value is silently ignored (no filter applied), consistent with
existing filter behavior in the codebase.

### `?provider=<value>`

Exact match on `MediaItem.provider`. Valid values from model choices:

```
local
cloudinary
cloudflare_images
cloudflare_stream
```

An invalid/unknown provider value yields an empty list — it does not raise a
400, consistent with the existing filter style in the project.

### `?search=<query>`

Case-insensitive `icontains` search across:

- `title_bs`, `title_en`, `title`
- `description_bs`, `description_en`
- `alt_text_bs`, `alt_text_en`
- `caption_bs`, `caption_en`
- `provider_public_id`
- `album__title_bs`, `album__title_en`, `album__slug`

No M2M joins are involved (MediaItem tags are stored as a JSONField, not a
relational M2M), so `.distinct()` is not required for the search filter.

---

## Query Optimization

The queryset is:

```python
MediaItem.objects
    .filter(
        media_type='image',
        album__gallery_type=Album.GALLERY_TYPE_IMAGE,
    )
    .select_related('album')
    .order_by('display_order', 'id')
```

- `media_type='image'` and `album__gallery_type=Album.GALLERY_TYPE_IMAGE` are
  both present, matching the original view's intent — this endpoint is
  image-specific and does not return video media.
- `select_related('album')` satisfies `gallery_id`, `gallery_slug`,
  `gallery_title_bs` fields in `AdminImageItemSerializer` without a second
  query per row.
- No `prefetch_related` is needed — `MediaItem.tags` is a JSONField, not a
  relational M2M.
- `.order_by('display_order', 'id')` matches `MediaItem.Meta.ordering`
  (`['display_order', 'id']`) and is declared explicitly on the queryset so
  the ordering is stable and explicit for pagination. `id` acts as a tie-breaker
  for rows with the same `display_order`.

---

## Tests Added

### `AdminImageItemListAPITests` — 17 tests

1. Anonymous user cannot access admin image list
2. Non-staff authenticated user cannot access admin image list
3. Staff user can access admin image list
4. Response is paginated (count / next / previous / results keys present)
5. Default page size is 50 (55 images → 50 on page 1, next link present)
6. `page_size` is respected
7. `page_size` is capped at 100
8. Endpoint returns only image media (video items are excluded)
9. `is_published=true` filters correctly
10. `is_published=false` filters correctly
11. `album=<pk>` filters correctly
12. Legacy `?gallery=<pk>` filter still works
13. `provider=` filters correctly
14. `search=` filters by media title
15. `search=` filters by album title
16. Pagination and filters work together (`is_published=true&page_size=2`)
17. Invalid `is_published` value is silently ignored (no filter applied)

---

## Validation Results

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery --verbosity=1
# Ran 229 tests in 97.971s
# OK
```

- Previous test count: 212
- New tests added: 17
- Total: 229 tests, 0 failures, 0 errors

---

## Backward Compatibility Notes

**Breaking change: list response shape.**

Before this change, `GET /api/gallery/admin/images/` returned a raw JSON array:

```json
[{ "id": 1, … }, …]
```

After this change it returns a paginated object:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{ "id": 1, … }]
}
```

Any existing admin frontend consuming this endpoint must be updated to read
`response.data.results` instead of `response.data`.

**Required follow-up:**

```
Phase 4D — Frontend admin image/media pagination support
```

The admin frontend must be updated to handle the paginated response shape and
expose page navigation controls before this backend change is deployed to an
environment with a live admin frontend.

**Legacy `?gallery=` filter preserved.** The existing `?gallery=<pk>` query
parameter continues to work as before. The new `?album=<pk>` parameter is
added as the canonical name.

**POST (upload) behavior unchanged.** The `perform_create` path and
`AdminImageItemWriteSerializer` are not modified. Existing upload tests pass.

---

## What Was Not Changed

- `gallery/models.py` — not touched
- `gallery/migrations/` — no migrations created
- `gallery/serializers.py` — not touched
- `gallery/urls.py` — not touched
- `gallery/admin.py` — not touched
- `gallery/public_urls.py` — not touched
- Public endpoints (`/api/public/`) — not changed
- Legacy public endpoints (`/api/gallery/videos/`, `/api/gallery/albums/`) — not changed
- Admin video endpoints — not changed
- Upload lifecycle — not modified
- Frontend files — not modified
- Caching — not added
- Search indexes — not added
- `AdminVideoPageNumberPagination` — not touched (Phase 4A artifact preserved)
- Other admin views (tags, video galleries, visitor messages) — not changed

---

## Scalability Notes

- **Admin image list is no longer unbounded**: `AdminImagePageNumberPagination`
  enforces a default page size of 50 and a hard cap of 100 per request.

- **Pagination is page-number based**: admin UI benefits from deterministic
  page navigation. Cursor pagination was not used here (cursor is used for
  public browsing).

- **All filters execute in the database**: `is_published`, `album`, `provider`,
  and `search` are all translated to SQL `WHERE` clauses. No objects are loaded
  into Python and then discarded.

- **Queryset uses `select_related` only where the serializer needs it**:
  `select_related('album')` is present because `AdminImageItemSerializer` reads
  `gallery_id`, `gallery_slug`, `gallery_title_bs`. No `prefetch_related` is
  added because `MediaItem.tags` is a JSONField — there is no M2M join.

- **Stable ordering**: `.order_by('display_order', 'id')` matches model
  `Meta.ordering` and ensures consistent pagination across pages even when two
  records share the same `display_order`.

- **No public endpoint behavior changed**: all `/api/public/` and legacy
  `/api/gallery/` public routes are unchanged.

- **No frontend files were changed**.

---

## Next Recommended Step

**Phase 4D — Frontend admin image/media pagination support**

```
GET /api/gallery/admin/images/?page=1&page_size=50
```

Update the admin frontend image list component to:
- Read `response.data.results` instead of `response.data`
- Display total count from `response.data.count`
- Render page navigation using `next` / `previous` links or page number controls
- Expose `is_published`, `album`, `provider`, and `search` filter inputs
