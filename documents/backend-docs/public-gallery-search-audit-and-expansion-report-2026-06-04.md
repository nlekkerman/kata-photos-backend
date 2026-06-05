# Public Gallery Search — Audit and Expansion Report

**Date:** 2026-06-04  
**Scope:** Backend only (`kata-photos-backend`)  
**Type:** Narrow search improvement — no migrations, no route changes, no frontend changes

---

## Files Changed

| File | Change |
|------|--------|
| `gallery/views.py` | Expanded `?search=` Q-filters for albums and videos; added `.distinct()` to `?tag=` branches |
| `gallery/tests.py` | Added `AlbumSearchCoverageTests` (13 tests) and `VideoSearchCoverageTests` (17 tests) |

No other files were modified. No migrations required (no model changes).

---

## Existing Search Behavior Found (Pre-Audit)

Both `AlbumListCreateView.get_queryset()` and `VideoClipListView.get_queryset()` already applied:

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(tags__name_bs__icontains=search) |
Q(tags__name_en__icontains=search)
```

with `.distinct()` on the search branch only (not on the `?tag=` branch).

The `?tag=` filter used `qs.filter(tags__slug=tag_slug)` without `.distinct()`.

Combined `?search=&tag=` already worked because both filters are applied sequentially to the same queryset.

---

## Model Field Audit

### Tag fields (all fields)
| Field | Type | Searchable? |
|-------|------|-------------|
| `name_bs` | CharField | ✓ Already included |
| `name_en` | CharField | ✓ Already included |
| `slug` | SlugField (unique) | ✓ Added |
| `created_at` / `updated_at` | DateTimeField | No — internal metadata |

### Album fields (public-relevant)
| Field | Type | Searchable? | Notes |
|-------|------|-------------|-------|
| `title_bs` | CharField | ✓ Already included | Primary Bosnian title |
| `title_en` | CharField | ✓ Already included | Primary English title |
| `description_bs` | TextField | ✓ Added | Public bilingual description |
| `description_en` | TextField | ✓ Added | Public bilingual description |
| `tags.name_bs` | M2M → Tag | ✓ Already included | |
| `tags.name_en` | M2M → Tag | ✓ Already included | |
| `tags.slug` | M2M → Tag | ✓ Added | Useful for programmatic search |
| `title` (legacy) | CharField | Excluded | Legacy admin-only field; bilingual fields are canonical |
| `description` (legacy) | TextField | Excluded | Legacy admin-only field |
| `seo_title_bs/en` | CharField | Excluded | SEO/admin-only; not public content |
| `seo_description_bs/en` | TextField | Excluded | SEO/admin-only; not public content |
| `seo_title/seo_description` (legacy) | CharField/TextField | Excluded | Legacy admin-only |
| `slug` | SlugField | Excluded | Not a content field |
| `gallery_type` | CharField | Excluded | Internal classification |
| `display_order` / `is_published` | Int / Bool | Excluded | Internal metadata |

### VideoClip fields (public-relevant)
| Field | Type | Searchable? | Notes |
|-------|------|-------------|-------|
| `title_bs` | CharField | ✓ Already included | |
| `title_en` | CharField | ✓ Already included | |
| `description_bs` | TextField | ✓ Added | |
| `description_en` | TextField | ✓ Added | |
| `album.title_bs` | FK → Album | ✓ Added | Nullable FK; NULL videos skip gracefully |
| `album.title_en` | FK → Album | ✓ Added | |
| `tags.name_bs` | M2M → Tag | ✓ Already included | |
| `tags.name_en` | M2M → Tag | ✓ Already included | |
| `tags.slug` | M2M → Tag | ✓ Added | |
| `cloudflare_uid` | CharField | Excluded | Internal Cloudflare identifier |
| `status` | CharField | Excluded | Internal processing state |
| `is_public` | BooleanField | Excluded | Already used as a queryset filter |

---

## Fields Included in Album Search (Post-Change)

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search) |
Q(tags__name_bs__icontains=search) |
Q(tags__name_en__icontains=search) |
Q(tags__slug__icontains=search)
```

---

## Fields Included in Video Search (Post-Change)

```python
Q(title_bs__icontains=search) |
Q(title_en__icontains=search) |
Q(description_bs__icontains=search) |
Q(description_en__icontains=search) |
Q(album__title_bs__icontains=search) |
Q(album__title_en__icontains=search) |
Q(tags__name_bs__icontains=search) |
Q(tags__name_en__icontains=search) |
Q(tags__slug__icontains=search)
```

---

## Fields Intentionally Excluded

| Field | Reason |
|-------|--------|
| `Album.title` | Legacy admin field; `title_bs`/`title_en` are canonical |
| `Album.description` | Legacy admin field; `description_bs`/`description_en` are canonical |
| `Album.seo_title_*`, `seo_description_*` | Admin/SEO metadata; not content for public search |
| `Album.slug` | URL identifier, not human content |
| `Album.gallery_type` | Internal classification, not searchable content |
| `VideoClip.cloudflare_uid` | Internal Cloudflare identifier |
| `VideoClip.status` | Internal state field |
| `FieldNote.*` | Out of scope; separate public endpoints |
| `MediaItem.*` | Out of scope; media items are nested under albums |

---

## Tag Filtering Behavior

`?tag=<slug>` works on both endpoints:

```
GET /api/gallery/albums/?tag=ptice    → albums tagged with slug 'ptice'
GET /api/gallery/videos/?tag=ptice    → videos tagged with slug 'ptice'
```

A `.distinct()` call was added to the tag filter branch (previously omitted). This prevents potential duplicate rows if future query plan changes cause fan-out.

---

## Search + Tag Combination Behavior

Both parameters apply sequentially on the same queryset:

1. `?tag=<slug>` narrows to items with that tag (JOIN + DISTINCT)
2. `?search=<query>` further narrows within that set (multi-field OR + DISTINCT)

Example:
```
GET /api/gallery/albums/?tag=ptice&search=orao
GET /api/gallery/videos/?tag=ptice&search=orao
```

Both work correctly. `.distinct()` is applied after any JOIN-producing filter.

---

## Tests Added / Updated

### `AlbumSearchCoverageTests` (13 new tests)

| Test | Coverage |
|------|----------|
| `test_search_by_title_bs` | Bosnian title match |
| `test_search_by_title_en` | English title match |
| `test_search_by_description_bs` | Bosnian description match |
| `test_search_by_description_en` | English description match |
| `test_search_by_description_en_altitude` | Second description match |
| `test_search_by_tag_name_bs` | Tag name (Bosnian) match |
| `test_search_by_tag_name_en` | Tag name (English) match |
| `test_search_by_tag_slug` | Tag slug match |
| `test_empty_search_returns_all_published` | Empty `?search=` no-op |
| `test_whitespace_only_search_returns_all_published` | Whitespace `?search=` stripped to no-op |
| `test_unknown_tag_returns_empty` | Unknown `?tag=` → empty list |
| `test_combined_tag_and_search` | `?tag=&search=` combined |
| `test_combined_tag_and_search_no_cross_match` | `?tag=` + mismatched `?search=` → empty |
| `test_no_duplicate_results_when_album_has_multiple_tags` | No duplicates from M2M join |
| `test_album_with_no_tags_not_excluded_from_empty_search` | Albums without tags visible by default |

### `VideoSearchCoverageTests` (17 new tests)

| Test | Coverage |
|------|----------|
| `test_search_by_title_bs` | Bosnian title match |
| `test_search_by_title_en` | English title match |
| `test_search_by_description_bs` | Bosnian description match |
| `test_search_by_description_en` | English description match |
| `test_search_by_album_title_bs` | Album FK Bosnian title match |
| `test_search_by_album_title_en` | Album FK English title match |
| `test_search_by_tag_name_bs` | Tag name (Bosnian) match |
| `test_search_by_tag_name_en` | Tag name (English) match |
| `test_search_by_tag_slug` | Tag slug match |
| `test_empty_search_returns_all_public_ready` | Empty `?search=` no-op |
| `test_whitespace_only_search_returns_all_public_ready` | Whitespace stripped |
| `test_unknown_tag_returns_empty` | Unknown `?tag=` → empty list |
| `test_combined_tag_and_search` | `?tag=&search=` combined |
| `test_combined_tag_and_search_no_cross_match` | `?tag=` + mismatched `?search=` → empty |
| `test_no_duplicate_results_when_video_has_multiple_tags` | No duplicates from M2M join |
| `test_video_with_no_tags_not_excluded_from_empty_search` | Videos without tags visible by default |
| `test_video_without_album_does_not_error_on_album_search` | NULL album FK handled gracefully |

---

## Commands Run

```
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test gallery --verbosity=2
```

---

## Validation Results

```
System check identified no issues (0 silenced).

Ran 110 tests in 48.448s
OK
```

All 110 tests passed. 30 new tests added (13 album + 17 video search coverage).

---

## Edge Cases Checked

| Scenario | Result |
|----------|--------|
| Empty `?search=` | Stripped to empty string → no filter applied → full list returned |
| Whitespace-only `?search=` | `.strip()` → empty string → no filter applied |
| Unknown `?tag=` slug | No matching rows → empty list (200 OK) |
| Albums with no tags | Returned by default list; not excluded by search unless search term actively mismatches |
| Videos with no tags | Same as above |
| Video with NULL album FK | `Q(album__title_bs__icontains=...)` does LEFT JOIN; NULL albums simply don't match — no 500 |
| Album with multiple tags | `.distinct()` on both tag and search branches prevents duplicate rows |
| Video with multiple tags | Same |
| `?search=&?tag=` combined | Applied sequentially; tag narrows, search further narrows; `.distinct()` covers JOINs |
| Case-insensitive matching | `icontains` handles uppercase/lowercase (SQLite collation dependent for non-ASCII) |
| Diacritics | SQLite `icontains` operates on byte level; exact diacritic matching depends on SQLite build. Not changed — no full-text search added. |

---

## Confirmation: No Frontend Files Touched

No files outside `gallery/views.py` and `gallery/tests.py` were modified. No frontend files exist in this repository.

---

## Confirmation: API Routes / Contracts Not Broken

- `GET /api/gallery/albums/?search=` — same parameter name, backward compatible (superset)
- `GET /api/gallery/videos/?search=` — same parameter name, backward compatible (superset)
- `GET /api/gallery/albums/?tag=` — same behavior, now with `.distinct()`
- `GET /api/gallery/videos/?tag=` — same behavior, now with `.distinct()`
- No URL patterns changed
- No serializer fields added or removed
- No HTTP status codes changed
- No permissions changed

---

## Known Limitations / Follow-Up Tasks

1. **Diacritic matching:** SQLite `icontains` is ASCII case-insensitive but not diacritic-folding. Searching `"suma"` will not match `"šuma"`. This is a known SQLite limitation. On PostgreSQL (production via Heroku), `icontains` maps to `ILIKE` which also does not fold diacritics by default. Full diacritic-insensitive search would require `unaccent` extension (PostgreSQL) or a custom field. This is a follow-up task.

2. **Pagination:** The video and album list views return unpaginated results. As the dataset grows, search without pagination could return large payloads. A follow-up task would be to add cursor or page-number pagination.

3. **Album `title` (legacy) field:** The `title` (no language suffix) field is still in the model but excluded from public search. If this field has content in production that is not duplicated in `title_bs`/`title_en`, a one-time data migration may be warranted.

4. **`?search=` on album detail / video detail:** Only list endpoints support `?search=`. Detail endpoints look up by slug/pk. This is correct and intentional.
