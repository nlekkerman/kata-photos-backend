# Query Optimization Phase 2B Report

## Summary

Added `select_related` and `prefetch_related` calls to six existing querysets in
`gallery/views.py` to eliminate N+1 queries for related objects already read by
the corresponding serializers. No API shapes, serializers, models, migrations, or
tests were changed.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/views.py` | Six `get_queryset` methods updated with `select_related` / `prefetch_related` |

---

## Querysets Optimized

### 1. `AlbumListCreateView.get_queryset` (GET)

```python
# Before
Album.objects.filter(is_published=True).prefetch_related('tags')

# After
Album.objects.filter(is_published=True).select_related('cover_media').prefetch_related('tags')
```

### 2. `AlbumRetrieveUpdateDestroyView.get_queryset` (GET)

```python
# Before
Album.objects.filter(is_published=True)

# After
Album.objects.filter(is_published=True).select_related('cover_media').prefetch_related('tags')
```

### 3. `AlbumMediaListCreateView.get_queryset` (GET)

```python
# Before
MediaItem.objects.filter(album=album, is_published=True)

# After
MediaItem.objects.filter(album=album, is_published=True).select_related('album')
```

### 4. `FieldNoteListView.get_queryset`

```python
# Before
FieldNote.objects.filter(is_published=True)

# After
FieldNote.objects.filter(is_published=True).select_related('cover_image')
```

### 5. `FieldNoteDetailView.get_queryset`

```python
# Before
FieldNote.objects.filter(is_published=True)

# After
FieldNote.objects.filter(is_published=True).select_related('cover_image')
```

### 6. `AdminVideoItemListView.get_queryset`

```python
# Before
VideoClip.objects.select_related('album').all()

# After
VideoClip.objects.select_related('album').prefetch_related('tags').all()
```

---

## Why These Optimizations

Each change was confirmed against the serializer that actually reads the
related field:

| View | Serializer | Related field accessed |
|---|---|---|
| `AlbumListCreateView` | `AlbumListSerializer` | `cover_media` (via `MediaCoverSerializer(source='cover_media')`), `tags` (already prefetched) |
| `AlbumRetrieveUpdateDestroyView` | `AlbumDetailSerializer` | `cover_media` (via `MediaCoverSerializer(source='cover_media')`), `tags` |
| `AlbumMediaListCreateView` | `MediaItemPublicSerializer` | `album.slug` (via `SlugRelatedField(source='album', slug_field='slug')`) |
| `FieldNoteListView` | `FieldNoteListSerializer` | `cover_image` (via `FieldNoteCoverSerializer(read_only=True)`) |
| `FieldNoteDetailView` | `FieldNoteDetailSerializer` | `cover_image` (via `FieldNoteCoverSerializer(read_only=True)`) |
| `AdminVideoItemListView` | `AdminVideoItemSerializer` | `album` (already select_related), `tags` (via `TagSerializer(many=True)`) |

`select_related` is used for FK / OneToOne relations (single JOIN).
`prefetch_related` is used for M2M relations (separate IN query per relation).

---

## API Contract Confirmation

No serializer fields were added, removed, or renamed. No response shapes
changed. The optimizations only affect how Django fetches the data that the
serializers already read.

---

## What Was Not Changed

- `gallery/serializers.py` — not touched
- `gallery/models.py` — not touched
- `gallery/public_urls.py` — not touched
- `gallery/urls.py` — not touched
- `gallery/tests.py` — not touched
- `config/settings.py` — not touched
- No migrations created
- No caching added
- No pagination added
- No new endpoints added
- No trigram / search indexes added
- Admin endpoints not redesigned
- Upload lifecycle not modified

---

## Validation Results

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery
# Ran 151 tests in 61.139s
# OK
```

- 151 tests run, 151 pass, 0 failures, 0 errors

---

## Next Recommended Step

**Phase 2C — `pg_trgm` GIN index for title search (optional)**

The `?search=<q>` filter on album and video list endpoints uses `icontains`
which requires a full sequential scan on text columns. A `GinIndex` using
PostgreSQL `pg_trgm` on `title_bs` / `title_en` would support efficient
substring search at scale. This requires enabling `django.contrib.postgres`
and the `pg_trgm` extension, and would be a separate migration with no model
field changes.
