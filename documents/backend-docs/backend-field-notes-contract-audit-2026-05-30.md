# Backend Field Notes / Articles Contract Audit

**Date:** 2026-05-30  
**Auditor:** GitHub Copilot (automated)  
**Repository:** `kata-photos-backend`  
**Scope:** Audit only — no source files changed.

---

## 1. Current Backend Gallery Structure Summary

Derived from direct source inspection.

**`gallery/models.py`** defines two models:

- `Album` — top-level container (slug, `is_published`, `display_order`, `cover_media` FK to `MediaItem`, bilingual fields, SEO fields, timestamps)
- `MediaItem` — individual photo/video (FK to `Album`, `media_type`, `is_published`, `display_order`, bilingual content fields, provider fields, media metadata fields, timestamps)

**`gallery/serializers.py`** defines:

- `resolve_translated(obj, field_name, lang)` — shared helper; returns `{field}_{lang}` falling back to `{field}_en`
- `_resolve_local_url(file_field, request)` — builds absolute URI for local files
- `_get_public_url(obj, request)` / `_get_thumbnail_url(obj, request)` — provider-aware URL resolution
- `MediaCoverSerializer` — minimal thumbnail + alt_text
- `AlbumListSerializer` — list fields: `id`, `slug`, `title`, `description`, `display_order`, `cover`
- `AlbumDetailSerializer` — adds `seo_title`, `seo_description`, `created_at`
- `MediaItemPublicSerializer` — all public media fields with translated method fields

**`gallery/views.py`** defines:

- `LangContextMixin` — extracts `?lang=` query param, validates against `('en', 'bs')`, falls back to `'en'`
- `AlbumListView` — filters `is_published=True`
- `AlbumDetailView` — slug lookup, filters `is_published=True`
- `AlbumMediaListView` — verifies album slug + `is_published=True`, filters media by `is_published=True`
- `MediaItemDetailView` — pk lookup, guards `album__is_published=True`

**`gallery/urls.py`** registers:

```
GET /api/gallery/albums/
GET /api/gallery/albums/<slug>/
GET /api/gallery/albums/<slug>/media/
GET /api/gallery/media/<pk>/
```

**`gallery/admin.py`** uses `@admin.register` with fieldsets grouped by language section and a collapsed Timestamps section.

**`config/urls.py`** mounts `gallery.urls` under `/api/gallery/`.

**Migrations present:**

- `0001_initial.py`
- `0002_alter_mediaitem_original_file.py`
- `0003_bilingual_fields.py` — added all `_en` / `_bs` columns to both models
- `0004_copy_content_to_en_fields.py` — data migration populating `_en` fields from legacy fields

**`python manage.py check` output:** `System check identified no issues (0 silenced)`

---

## 2. Existing Album/MediaItem Translation Pattern

Translation is handled entirely in Python, not via a translation library. The pattern is:

1. **Storage**: every translatable field has two explicit DB columns — `{field}_en` and `{field}_bs`.  
   Example from `Album`: `title_en`, `title_bs`, `description_en`, `description_bs`, `seo_title_en`, `seo_title_bs`, etc.

2. **Resolution**: a shared function in `serializers.py` resolves the correct language value at serialization time:
   ```python
   def resolve_translated(obj, field_name, lang):
       value = getattr(obj, f"{field_name}_{lang}", "")
       fallback = getattr(obj, f"{field_name}_en", "")
       return value or fallback
   ```
   - Falls back to `_en` when the requested language field is empty.
   - Falls back to `_en` when the requested language is unsupported.

3. **Public exposure**: serializers expose only the canonical translated field name (e.g., `title`, `description`). The `_en` / `_bs` raw columns are never returned by public serializers.

4. **Language negotiation**: `LangContextMixin.get_serializer_context()` reads `?lang=` from the query string, validates against `('en', 'bs')`, and silently falls back to `'en'` for any other value. The resolved lang is passed into serializer context as `context['lang']`.

5. **Legacy fields**: `Album` and `MediaItem` still carry the original non-suffixed fields (`title`, `description`, `alt_text`, `caption`) from before the bilingual migration. These are present in the DB but not returned by public serializers. The `__str__` method on both models uses `title_en or title` as a safe fallback.

**Summary:** the translation pattern is explicit, code-level, and consistent. It can be replicated exactly for `FieldNote` with zero new infrastructure.

---

## 3. Existing Public Endpoint Pattern

| Endpoint | View | Serializer | Filter | Lookup |
|---|---|---|---|---|
| `GET /api/gallery/albums/` | `AlbumListView` | `AlbumListSerializer` | `is_published=True` | — |
| `GET /api/gallery/albums/<slug>/` | `AlbumDetailView` | `AlbumDetailSerializer` | `is_published=True` | slug |
| `GET /api/gallery/albums/<slug>/media/` | `AlbumMediaListView` | `MediaItemPublicSerializer` | album+media both published | slug |
| `GET /api/gallery/media/<pk>/` | `MediaItemDetailView` | `MediaItemPublicSerializer` | `is_published=True`, `album__is_published=True` | pk |

**Patterns observed:**

- All views use `generics.ListAPIView` or `generics.RetrieveAPIView`. No `ViewSet` or `Router` used.
- Language mixin is applied as a leftmost base class: `class FooView(LangContextMixin, generics.ListAPIView)`.
- `get_queryset()` handles all filtering.
- Slug-based detail views use `lookup_field = 'slug'`.
- No authentication or permission classes are set explicitly — DRF defaults apply (public read).
- No pagination class is configured in `settings.py` or on views (confirmed: `settings.py` does not define `REST_FRAMEWORK` pagination settings; the gallery list views return all results).

---

## 4. Recommended `FieldNote` Model Fields

Based on source inspection of existing patterns and the requirements specification.

```python
class FieldNote(models.Model):
    slug = models.SlugField(max_length=200, unique=True)

    # Bilingual content — follows exact Album/MediaItem pattern
    title_en = models.CharField(max_length=200)
    title_bs = models.CharField(max_length=200, blank=True)
    excerpt_en = models.TextField(blank=True)
    excerpt_bs = models.TextField(blank=True)
    body_en = models.TextField()
    body_bs = models.TextField(blank=True)

    # Location — not language-specific (place name, typically consistent)
    location = models.CharField(max_length=200, blank=True)

    # Publishing
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    # Optional cover image
    cover_image = models.ForeignKey(
        'MediaItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cover_for_field_notes',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title_en or f'FieldNote {self.pk}'
```

**Field rationale:**

| Field | Rationale |
|---|---|
| `slug` | Unique URL key; matches Album pattern; used for detail endpoint |
| `title_en` | Required; primary language consistent with `Album`/`MediaItem` where `title_en` is the de-facto required field |
| `title_bs` | Optional at DB level; `resolve_translated` falls back to `_en` |
| `excerpt_en` / `excerpt_bs` | Short summary for list views; blank allowed |
| `body_en` | Main article body; not blank at model level (see edge cases); required for meaningful published content |
| `body_bs` | Optional; fallback to `body_en` via `resolve_translated` |
| `location` | Consistent with wildlife context; single-language (place names are typically not translated) |
| `is_published` | Matches `Album` and `MediaItem` exactly; guards public visibility |
| `published_at` | Nullable datetime; allows scheduling content; used for ordering; distinct from `created_at` |
| `cover_image` | FK to `MediaItem` with `SET_NULL`; exactly mirrors `Album.cover_media` pattern |
| `created_at` / `updated_at` | `auto_now_add` / `auto_now`; matches both existing models |

**Deferred (not recommended at this stage):**

- `related_album` — FK to `Album`; could link an article to a gallery; deferred because it adds join complexity with no confirmed frontend need
- `related_media` — M2M to `MediaItem`; deferred; increases migration surface with no confirmed frontend need
- `tags` / `categories` — deferred; `MediaItem.tags` uses `JSONField(default=list)` as precedent but search/filter UI is not planned
- `seo_title_en` / `seo_title_bs` / `seo_description_en` / `seo_description_bs` — deferred; `Album` has these but `FieldNote` frontend SEO strategy is unknown
- `location_bs` — location field is not split by language; if place names need translation this can be added in a follow-up migration

---

## 5. Recommended Public Serializers

Two serializers following the exact existing pattern:

### `FieldNoteListSerializer`

```python
class FieldNoteListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    cover_image = FieldNoteCoverSerializer(read_only=True)

    class Meta:
        model = FieldNote
        fields = ['id', 'slug', 'title', 'excerpt', 'location', 'published_at', 'cover_image']

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_excerpt(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'excerpt', lang)
```

### `FieldNoteDetailSerializer`

```python
class FieldNoteDetailSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    cover_image = FieldNoteCoverSerializer(read_only=True)

    class Meta:
        model = FieldNote
        fields = ['id', 'slug', 'title', 'excerpt', 'body', 'location', 'published_at', 'cover_image']

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_excerpt(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'excerpt', lang)

    def get_body(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'body', lang)
```

### `FieldNoteCoverSerializer`

A minimal cover serializer analogous to `MediaCoverSerializer`:

```python
class FieldNoteCoverSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    alt_text = serializers.SerializerMethodField()

    class Meta:
        model = MediaItem
        fields = ['id', 'thumbnail_url', 'alt_text']

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        return _get_thumbnail_url(obj, request)

    def get_alt_text(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'alt_text', lang)
```

**Public response shape (list):**

```json
[
  {
    "id": 1,
    "slug": "dawn-on-zelengora",
    "title": "Dawn on Zelengora",
    "excerpt": "Early morning mist across the plateau.",
    "location": "Zelengora, Bosnia",
    "published_at": "2026-05-30T10:00:00Z",
    "cover_image": {
      "id": 42,
      "thumbnail_url": "https://example.com/media/gallery/originals/photo.jpg",
      "alt_text": "A lynx at dawn"
    }
  }
]
```

**Public response shape (detail, adds `body`):**

```json
{
  "id": 1,
  "slug": "dawn-on-zelengora",
  "title": "Dawn on Zelengora",
  "excerpt": "Early morning mist across the plateau.",
  "body": "Full article text here...",
  "location": "Zelengora, Bosnia",
  "published_at": "2026-05-30T10:00:00Z",
  "cover_image": null
}
```

Neither `title_en`, `title_bs`, `body_en`, `body_bs` nor any `_lang`-suffixed field appears in public output. This is confirmed consistent with the existing `Album` and `MediaItem` serializer strategy.

---

## 6. Recommended Public Endpoints

```
GET /api/gallery/field-notes/              → FieldNoteListView
GET /api/gallery/field-notes/<slug>/       → FieldNoteDetailView
```

Both support `?lang=en` and `?lang=bs` query params via the existing `LangContextMixin`.

**Mounted in `gallery/urls.py`** (no change to `config/urls.py` required):

```python
path('field-notes/', FieldNoteListView.as_view(), name='fieldnote-list'),
path('field-notes/<slug:slug>/', FieldNoteDetailView.as_view(), name='fieldnote-detail'),
```

**Views:**

```python
class FieldNoteListView(LangContextMixin, generics.ListAPIView):
    serializer_class = FieldNoteListSerializer

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)

class FieldNoteDetailView(LangContextMixin, generics.RetrieveAPIView):
    serializer_class = FieldNoteDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)
```

The default `Meta.ordering = ['-published_at', '-created_at']` handles descending chronological order automatically. No `order_by()` override is needed in `get_queryset()`.

**Invalid slug** returns HTTP 404 automatically via DRF `RetrieveAPIView` when `get_queryset()` returns an empty queryset.

**Draft notes** are excluded by `filter(is_published=True)` — same mechanism as `Album`.

---

## 7. Should `FieldNote` Live in the Existing `gallery` App or a New App?

**Recommendation: add to the existing `gallery` app.**

Rationale:

- The existing app is small (2 models, 4 views, 4 endpoints). Adding one model keeps the total at 3 models — well within a manageable single-app boundary.
- `FieldNote.cover_image` is a FK to `MediaItem`, which lives in `gallery`. Cross-app FKs are valid Django but add import complexity and migration dependency tracking for minimal gain at this scale.
- The public URL namespace is already `/api/gallery/`. Adding `field-notes/` there is semantically coherent: field notes are gallery-adjacent author content.
- No existing code in `gallery` is unrelated to this domain; there is no sprawl that would justify extraction.
- A new app (`articles`, `field_notes`) would require new `INSTALLED_APPS` entry, new `urls.py` include in `config/urls.py`, and a new migration tree — 3+ file touches with no architectural benefit at this stage.

**When to reconsider:** if `FieldNote` later grows its own set of sub-resources (e.g., comments, tags with admin UI, rich text media), creating a dedicated app at that point is appropriate.

---

## 8. Should `FieldNote` Support Draft/Published State?

**Yes — `is_published = BooleanField(default=False)` is required and sufficient.**

Rationale:

- The existing `Album` and `MediaItem` models use exactly this pattern. There is no staged workflow, soft-delete, or status enum in the current codebase.
- Admin authors need a way to save work-in-progress without exposing it publicly.
- A `published_at` datetime field (nullable) serves a distinct but complementary purpose: it records when the note became public and drives ordering.

**Interaction between `is_published` and `published_at`:**

- A note with `is_published=False` is never returned by public endpoints, regardless of `published_at`.
- A note with `is_published=True` and `published_at=None` is publicly visible but will sort to the end of the default ordering (NULLs sort last in PostgreSQL; SQLite behaviour is similar). Implementation must handle this gracefully — see edge cases.
- Setting `published_at` automatically when `is_published` is toggled to `True` is a convenience that can be handled in the admin `save_model()` or as a signal. This is deferred to implementation.

---

## 9. Should `FieldNote` Support an Optional Cover Image?

**Yes — `cover_image` FK to `MediaItem` is recommended.**

Rationale:

- `Album.cover_media` is a direct precedent: same FK to `MediaItem`, same `null=True, blank=True, on_delete=SET_NULL` pattern.
- `FieldNoteCoverSerializer` (see §5) mirrors `MediaCoverSerializer` exactly. The provider-aware `_get_thumbnail_url` helper is already reusable.
- The field is fully optional (`null=True, blank=True`). A note with no cover image returns `"cover_image": null` in the public response.
- The alternative (a raw URL field or a base64 field) would diverge from the established media management pattern.

**Not recommended at this stage:**

- Uploading images directly to `FieldNote` via a separate `FileField`/`ImageField` — this duplicates the media pipeline that `MediaItem` already owns.
- Embedding inline images in `body_en`/`body_bs` via Markdown or HTML — deferred; requires frontend rendering decisions.

---

## 10. Should `FieldNote` Optionally Link to `Album` or `MediaItem`?

**Deferred. Do not add `related_album` or `related_media` in the first implementation.**

Rationale:

- There is no confirmed frontend component that renders "linked gallery" or "featured photo" within a field note view.
- A `related_album` FK introduces a nullable FK and a serializer field that may be empty for most notes, increasing surface area for no immediate return.
- A M2M `related_media` requires an additional join table migration and a nested serializer with ordered results — disproportionate for an initial feature.
- `cover_image` already provides one meaningful link to `MediaItem`.

**When to add:** if the frontend designs a "Gallery" section inside a field note article view, add `related_album` as a FK at that time. It will be a single-migration, single-serializer-field addition.

---

## 11. Required Migrations

Exactly one new migration is needed:

**`gallery/migrations/0005_fieldnote.py`** — auto-generated via `python manage.py makemigrations`

Operations it must contain:

1. `CreateModel` for `FieldNote` with all fields listed in §4.
2. `AlterModelOptions` to set `ordering = ['-published_at', '-created_at']` (or this can be embedded in `CreateModel`).

No data migration is required (new model, no existing data to transform).

No changes to existing migrations.

Dependency: `('gallery', '0004_copy_content_to_en_fields')`.

---

## 12. Admin Registration Recommendation

Register `FieldNote` with `@admin.register` in `gallery/admin.py` following the established fieldset pattern:

```python
@admin.register(FieldNote)
class FieldNoteAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'slug', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title_en', 'slug', 'location')
    ordering = ('-published_at', '-created_at')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('title_en',)}
    fieldsets = (
        ('Publishing', {
            'fields': ('slug', 'is_published', 'published_at', 'cover_image'),
        }),
        ('English Content', {
            'fields': ('title_en', 'excerpt_en', 'body_en'),
        }),
        ('Bosnian Content', {
            'fields': ('title_bs', 'excerpt_bs', 'body_bs'),
        }),
        ('Location', {
            'fields': ('location',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
```

Notes:
- `prepopulated_fields = {'slug': ('title_en',)}` — convenience feature consistent with how Django admin works for slugs; not present on existing models but safe to add here.
- `list_display` matches the `AlbumAdmin` structure (`name`, `slug`, `is_published`, timestamp).
- No inline for related media at this stage.

---

## 13. Edge Cases Implementation Must Handle

| # | Scenario | Expected Behaviour |
|---|---|---|
| 1 | No field notes exist | List endpoint returns `[]` with HTTP 200 |
| 2 | Only unpublished field notes exist | List endpoint returns `[]` with HTTP 200; `is_published=False` rows excluded by `get_queryset` |
| 3 | One published field note exists | List returns array with 1 item |
| 4 | Multiple published field notes exist | List returns all, ordered `-published_at`, `-created_at` |
| 5 | Invalid slug in detail endpoint | HTTP 404 (DRF default via empty queryset + `get_object_or_404`) |
| 6 | Unsupported `?lang=` value (e.g., `?lang=fr`) | `LangContextMixin` silently falls back to `'en'`; no error |
| 7 | Missing Bosnian translation (`title_bs=""`) | `resolve_translated` falls back to `title_en`; no empty string returned if `_en` is populated |
| 8 | Missing English translation (`title_en=""`) | `resolve_translated` returns `""`; list/detail will surface an empty string — author must ensure `title_en` is always populated before publishing |
| 9 | Empty `excerpt` | Both `excerpt_en` and `excerpt_bs` are `blank=True`; empty string is valid; no fallback required |
| 10 | Published note with `body_en=""` | Model constraint: `body_en = models.TextField()` does not enforce non-blank at DB level; implementation should add model-level validation or admin-level `clean()` to block publishing with empty body |
| 11 | Future frontend must not show fake fallback notes | `is_published=False` is sufficient if frontend calls this API instead of static arrays; no additional backend mechanism needed |
| 12 | Ordering by `published_at` descending | `Meta.ordering` handles this; notes with `published_at=None` sort to the bottom in SQLite (NULL last in ascending, NULL first in descending — **verify behaviour**); consider `COALESCE(published_at, created_at)` ordering if NULLs are problematic |
| 13 | Draft notes must not appear publicly | `filter(is_published=True)` in `get_queryset` — same mechanism as `Album` |
| 14 | Published note with `published_at=None` | Returns in public list but sorts to end; `published_at: null` appears in response; frontend must handle null `published_at` gracefully |
| 15 | Cover image `null` | `cover_image: null` in response; `FieldNoteCoverSerializer` is not called; handled by DRF `SerializerMethodField` returning `None` for null FK |
| 16 | No frontend URL construction for media fields | `cover_image.thumbnail_url` is built server-side via `_get_thumbnail_url(obj, request)` using `request.build_absolute_uri()`; frontend receives a full absolute URL |
| 17 | `cover_image` FK points to an unpublished `MediaItem` | No guard is implemented in `Album` either; implementation may choose to add `cover_image__is_published=True` to admin validation or accept that an unpublished media item can still appear as a cover |

---

## 14. Recommended Next Implementation Phase

**Target:** one narrow feature, ~5–7 files.

### Files to touch

| File | Change |
|---|---|
| `gallery/models.py` | Add `FieldNote` class |
| `gallery/serializers.py` | Add `FieldNoteCoverSerializer`, `FieldNoteListSerializer`, `FieldNoteDetailSerializer` |
| `gallery/views.py` | Add `FieldNoteListView`, `FieldNoteDetailView` |
| `gallery/urls.py` | Add 2 URL patterns |
| `gallery/admin.py` | Add `FieldNoteAdmin` with `@admin.register` |
| `gallery/migrations/0005_fieldnote.py` | Auto-generated via `makemigrations` |

**Total: 6 files** (5 edited, 1 created by Django).

### Suggested implementation order

1. `models.py` — add `FieldNote`; run `makemigrations`; run `migrate`; run `python manage.py check`
2. `serializers.py` — add serializers
3. `views.py` — add views
4. `urls.py` — add URL patterns
5. `admin.py` — add admin registration
6. Manual admin test: create a draft note, verify it does not appear on API; publish it, verify it appears

### Hard cap note

6 files is well within the 8-file hard cap. No splitting is needed. `serializers.py` will grow by ~40–50 lines; it is currently ~130 lines, well within a manageable size.

---

## 15. Confirmation That No Source Files Were Changed

The following files were read during this audit:

- `gallery/models.py` — read only
- `gallery/serializers.py` — read only
- `gallery/views.py` — read only
- `gallery/urls.py` — read only
- `gallery/admin.py` — read only
- `gallery/migrations/0003_bilingual_fields.py` — read only (representative migration)
- `config/urls.py` — read only
- `config/settings.py` — read only (lines 1–100)

The following read-only command was executed:

```
python manage.py check
```

Output: `System check identified no issues (0 silenced)`

**No source files were modified. No migrations were created. No models were added.**

---

*End of audit.*
