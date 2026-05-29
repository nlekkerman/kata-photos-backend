# Gallery Bilingual Content Audit — 2026-05-29

**Status:** Audit only — no code changed.  
**Languages in scope:** English (`en`), Bosnian (`bs`)  
**Source files inspected:** `gallery/models.py`, `gallery/serializers.py`, `gallery/views.py`, `gallery/urls.py`, `gallery/admin.py`, `config/settings.py`, `config/urls.py`

---

## 1. Current Model Fields

All field data derived from `gallery/models.py`.

### Album

| Field | Type | Bilingual? |
|---|---|---|
| `id` | Auto PK | No — identifier |
| `title` | `CharField(max_length=200)` | **Yes** |
| `slug` | `SlugField(unique=True)` | No — URL identifier, language-neutral |
| `description` | `TextField(blank=True)` | **Yes** |
| `is_published` | `BooleanField` | No |
| `display_order` | `PositiveIntegerField` | No |
| `cover_media` | `ForeignKey('MediaItem')` | No |
| `seo_title` | `CharField(max_length=200, blank=True)` | **Yes** — served to search engines per language |
| `seo_description` | `TextField(blank=True)` | **Yes** — served to search engines per language |
| `created_at` | `DateTimeField(auto_now_add=True)` | No |
| `updated_at` | `DateTimeField(auto_now=True)` | No |

### MediaItem

| Field | Type | Bilingual? |
|---|---|---|
| `id` | Auto PK | No — identifier |
| `album` | `ForeignKey(Album)` | No |
| `media_type` | `CharField(choices)` | No — machine value |
| `title` | `CharField(max_length=200, blank=True)` | **Yes** |
| `description` | `TextField(blank=True)` | **Yes** |
| `alt_text` | `CharField(max_length=500, blank=True)` | **Yes** — accessibility requirement per language |
| `caption` | `CharField(max_length=500, blank=True)` | **Yes** |
| `tags` | `JSONField(default=list)` | Decision point — see section 8 |
| `is_published` | `BooleanField` | No |
| `display_order` | `PositiveIntegerField` | No |
| `provider` | `CharField(choices)` | No — technical |
| `provider_public_id` | `CharField(max_length=500)` | No — technical |
| `original_file` | `FileField` | No — binary asset |
| `public_url` | `URLField` | No — computed/stored URL |
| `thumbnail_url` | `URLField` | No — computed/stored URL |
| `width` | `PositiveIntegerField` | No — numeric |
| `height` | `PositiveIntegerField` | No — numeric |
| `duration_seconds` | `FloatField` | No — numeric |
| `file_size` | `PositiveIntegerField` | No — numeric |
| `created_at` | `DateTimeField` | No |
| `updated_at` | `DateTimeField` | No |

---

## 2. Current Serializers and Public API Content Fields

All field data derived from `gallery/serializers.py`.

### `MediaCoverSerializer`

Nested inside album responses for `cover_media`.

| Field | Source |
|---|---|
| `id` | Model PK |
| `thumbnail_url` | `SerializerMethodField` — computed via `_get_thumbnail_url` |
| `alt_text` | `MediaItem.alt_text` — **bilingual candidate** |

### `AlbumListSerializer`

Used by `GET /api/gallery/albums/`.

| Field | Source |
|---|---|
| `id` | Model PK |
| `slug` | `Album.slug` |
| `title` | `Album.title` — **bilingual candidate** |
| `description` | `Album.description` — **bilingual candidate** |
| `display_order` | `Album.display_order` |
| `cover` | Nested `MediaCoverSerializer` |

### `AlbumDetailSerializer`

Used by `GET /api/gallery/albums/<slug>/`.

| Field | Source |
|---|---|
| `id` | Model PK |
| `slug` | `Album.slug` |
| `title` | `Album.title` — **bilingual candidate** |
| `description` | `Album.description` — **bilingual candidate** |
| `seo_title` | `Album.seo_title` — **bilingual candidate** |
| `seo_description` | `Album.seo_description` — **bilingual candidate** |
| `display_order` | `Album.display_order` |
| `cover` | Nested `MediaCoverSerializer` |
| `created_at` | `Album.created_at` |

### `MediaItemPublicSerializer`

Used by `GET /api/gallery/albums/<slug>/media/` and `GET /api/gallery/media/<id>/`.

| Field | Source |
|---|---|
| `id` | Model PK |
| `album_slug` | `SlugRelatedField` on `album` |
| `media_type` | `MediaItem.media_type` |
| `title` | `MediaItem.title` — **bilingual candidate** |
| `description` | `MediaItem.description` — **bilingual candidate** |
| `alt_text` | `MediaItem.alt_text` — **bilingual candidate** |
| `caption` | `MediaItem.caption` — **bilingual candidate** |
| `tags` | `MediaItem.tags` — decision point |
| `public_url` | `SerializerMethodField` — computed via `_get_public_url` |
| `thumbnail_url` | `SerializerMethodField` — computed via `_get_thumbnail_url` |
| `width` | `MediaItem.width` |
| `height` | `MediaItem.height` |
| `display_order` | `MediaItem.display_order` |

### Language selection — current state

No language selection exists anywhere in the codebase. No `?lang=` handling in views, no language-aware serializer logic. All four views filter only on `is_published=True`. `config/settings.py` has `USE_I18N = True` and `LANGUAGE_CODE = 'en-us'` — standard Django defaults, unused for content delivery.

---

## 3. Bilingual Field Summary

**Album — fields that must become bilingual:**

- `title`
- `description`
- `seo_title`
- `seo_description`

**MediaItem — fields that must become bilingual:**

- `title`
- `description`
- `alt_text`
- `caption`

**`tags` — deferred decision** (see section 8).

**Fields that stay language-neutral (no change):**

- All identifiers: `id`, `slug`, `album_slug`
- All technical/provider fields: `provider`, `provider_public_id`, `public_url`, `thumbnail_url`, `original_file`
- All numeric metadata: `width`, `height`, `duration_seconds`, `file_size`, `display_order`
- All timestamps: `created_at`, `updated_at`
- All boolean flags: `is_published`
- All FK relations: `album`, `cover_media`
- `media_type` — machine value

---

## 4. Recommended Bilingual Model Strategy

### Options evaluated

**Option A — Explicit `_en` / `_bs` column pairs**

Add `title_en`, `title_bs`, `description_en`, `description_bs`, etc. as separate model fields.

**Option B — JSONField per field**

Store `title = JSONField` as `{"en": "...", "bs": "..."}`.

**Option C — Separate translation table**

Separate `AlbumTranslation` / `MediaItemTranslation` model with `language` + translated fields.

### Recommendation: Option A — explicit `_en` / `_bs` column pairs

**Rationale:**

1. **Only two languages.** The main argument against explicit columns ("schema explosion") does not apply at two languages. The total new columns are 8 on Album and 8 on MediaItem.
2. **No extra packages.** JSONField translation (Option B) and separate translation tables (Option C) both require custom serializer logic or packages. Option A needs zero new dependencies.
3. **Django admin works natively.** Standard `CharField` and `TextField` fields render without custom widgets. `fieldsets` in `AlbumAdmin` and `MediaItemAdmin` can group English and Bosnian fields visually.
4. **Serializer resolution is trivial.** `title = getattr(obj, f'title_{lang}') or obj.title_en` — one line per field, no JSON parsing.
5. **Database queries are direct column access.** No JSON path extraction, no subqueries, no joins.
6. **Migration path is safe and reversible.** Existing `title` → `title_en` via a data migration; `title_bs` starts blank; original field can coexist temporarily.
7. **API contract is unchanged.** Serializer outputs `title`, `description`, etc. — frontend never sees `_en` / `_bs` suffixes.

**Rejected reasons for alternatives:**
- Option B (JSONField): admin exposes raw JSON, no field-level validation per language, harder to query, violates "admin must remain usable without custom dashboard" constraint.
- Option C (translation table): requires joins on every query, more complex admin (inline or separate admin class), adds model complexity that is not justified for two languages.

### Proposed new fields

**Album — add:**

```python
title_en = CharField(max_length=200)
title_bs = CharField(max_length=200, blank=True)
description_en = TextField(blank=True)
description_bs = TextField(blank=True)
seo_title_en = CharField(max_length=200, blank=True)
seo_title_bs = CharField(max_length=200, blank=True)
seo_description_en = TextField(blank=True)
seo_description_bs = TextField(blank=True)
```

**MediaItem — add:**

```python
title_en = CharField(max_length=200, blank=True)
title_bs = CharField(max_length=200, blank=True)
description_en = TextField(blank=True)
description_bs = TextField(blank=True)
alt_text_en = CharField(max_length=500, blank=True)
alt_text_bs = CharField(max_length=500, blank=True)
caption_en = CharField(max_length=500, blank=True)
caption_bs = CharField(max_length=500, blank=True)
```

**`title_bs` blank=True** on Album because Bosnian content will be populated after migration — it should not be required at the database level.

---

## 5. Recommended API Language-Selection Strategy

### Query parameter: `?lang=`

All four public endpoints accept an optional `?lang=` query parameter:

```
GET /api/gallery/albums/?lang=bs
GET /api/gallery/albums/<slug>/?lang=en
GET /api/gallery/albums/<slug>/media/?lang=bs
GET /api/gallery/media/<id>/?lang=en
```

**Behaviour rules:**

| Input | Behaviour |
|---|---|
| `?lang=en` | Serve English fields |
| `?lang=bs` | Serve Bosnian fields |
| No `?lang=` | Default to `en` |
| `?lang=fr` (invalid) | Fall back to `en` — no validation error |
| `?lang=EN` (wrong case) | Normalise to lowercase `en` |

**Fallback within a record:** If `title_bs` is blank on a specific record, fall back to `title_en`. This prevents empty strings appearing in the API when Bosnian content is not yet entered. The fallback is silent — no error, no flag in the response.

**Implementation point:** `lang` is resolved once in the view and injected into serializer context as `context['lang']`. Serializers read from `self.context.get('lang', 'en')`. Views do not duplicate resolution logic.

**No URL-path-based language routing** (`/bs/api/gallery/...`). Path-based routing changes URL structure and complicates URL configuration. Query parameter is simpler and does not affect routing.

**No `Accept-Language` header routing.** Header-based routing is harder to test, harder to pass from a frontend SPA, and complicates caching. Query parameter is explicit and cacheable per `lang` value.

---

## 6. Recommended Admin Strategy

### Fieldsets for bilingual grouping

`AlbumAdmin` and `MediaItemAdmin` gain `fieldsets` that visually separate English and Bosnian content. No custom dashboard, no extra packages — standard Django admin `fieldsets`.

**Example fieldsets structure for AlbumAdmin:**

```python
fieldsets = (
    (None, {
        'fields': ('slug', 'is_published', 'display_order', 'cover_media')
    }),
    ('English Content', {
        'fields': ('title_en', 'description_en', 'seo_title_en', 'seo_description_en')
    }),
    ('Bosnian Content', {
        'fields': ('title_bs', 'description_bs', 'seo_title_bs', 'seo_description_bs')
    }),
    ('Timestamps', {
        'fields': ('created_at', 'updated_at'),
        'classes': ('collapse',)
    }),
)
```

**Example fieldsets structure for MediaItemAdmin:**

```python
fieldsets = (
    (None, {
        'fields': ('album', 'media_type', 'is_published', 'display_order', 'tags')
    }),
    ('English Content', {
        'fields': ('title_en', 'description_en', 'alt_text_en', 'caption_en')
    }),
    ('Bosnian Content', {
        'fields': ('title_bs', 'description_bs', 'alt_text_bs', 'caption_bs')
    }),
    ('Media / Provider', {
        'fields': ('provider', 'provider_public_id', 'original_file', 'public_url', 'thumbnail_url', 'width', 'height', 'duration_seconds', 'file_size')
    }),
    ('Timestamps', {
        'fields': ('created_at', 'updated_at'),
        'classes': ('collapse',)
    }),
)
```

Admin remains fully usable without a custom dashboard. All fields are standard field types. The Bosnian section is visible but blank until content is entered.

---

## 7. Migration Impact

### Step sequence

1. **Add `_en` / `_bs` fields alongside existing `title`, `description`, etc.**  
   New fields: `title_en`, `title_bs`, `description_en`, `description_bs`, `seo_title_en`, `seo_title_bs`, `seo_description_en`, `seo_description_bs` on Album; same pattern on MediaItem.  
   All new fields are `blank=True` initially to avoid breaking existing records.

2. **Write a data migration that copies existing field values into the `_en` fields.**  
   `Album.objects.update(title_en=F('title'), description_en=F('description'), ...)` — one pass, no Python loop required.  
   `MediaItem.objects.update(title_en=F('title'), alt_text_en=F('alt_text'), ...)` similarly.

3. **Update serializers to read from `_en` / `_bs` fields and output canonical names.**  
   Serializer `get_title(obj)` returns `getattr(obj, f'title_{lang}') or obj.title_en`.  
   API contract (field names in response) is unchanged.

4. **Update admin to use `fieldsets` with `_en` / `_bs` grouping.**

5. **After all serializers and admin are confirmed working, drop the original `title`, `description`, `alt_text`, `caption`, `seo_title`, `seo_description` columns in a follow-up migration.**  
   This is a separate migration run only after verifying data integrity.

### Backward compatibility window

During the transition (steps 1–4 complete, step 5 not yet run):
- Old columns still exist in DB — no data loss
- API already returns from `_en` fields — output is identical to current output
- Original columns can be removed safely once step 5 is confirmed

### No foreign key or index changes

Only `CharField` and `TextField` additions. No FK changes, no unique constraints, no index changes. Migration is low risk.

---

## 8. Tags Field — Deferred Decision

`MediaItem.tags` is a `JSONField(default=list)` storing a flat list of strings (e.g. `["nature", "wildlife"]`).

**Two options:**

| Option | Shape | Notes |
|---|---|---|
| Language-neutral tags | `["nature", "wildlife"]` — unchanged | Tags are used as identifiers, not display text. Frontend would need to translate tag display strings separately. |
| Per-language tags | `{"en": ["nature", "wildlife"], "bs": ["priroda", "divlje životinje"]}` | Tags become bilingual display strings. Requires changing `JSONField` shape — breaking for existing data. |

**Recommendation for MVP:** Keep `tags` language-neutral. Tags function as identifiers/filters, not prose content. Bosnian display names for tags are a frontend concern (a lookup table or translation file). If bilingual tag display becomes a requirement, the field can be migrated to the `{"en": [...], "bs": [...]}` shape later without breaking the model structure.

---

## 9. Frontend Impact

**What frontend sends:** Add `?lang=${currentLanguage}` to every gallery API request.

**What frontend reads:** Identical field names as today — `title`, `description`, `alt_text`, `caption`, `seo_title`, `seo_description`. No `_en` or `_bs` suffixes visible to frontend.

**What frontend must never do:**
- Choose between `title_en` and `title_bs` — backend resolves this
- Construct fallback content — backend fallback (bs → en) is silent and server-side
- Build media URLs — `public_url` and `thumbnail_url` remain backend-computed, unchanged

**Request examples:**

```
GET /api/gallery/albums/?lang=bs
GET /api/gallery/albums/wildlife/?lang=bs
GET /api/gallery/albums/wildlife/media/?lang=bs
GET /api/gallery/media/10/?lang=bs
```

**Response shape is unchanged.** Only field values change based on `lang`.

---

## 10. Risks and Anti-Patterns

| Risk | Description | Mitigation |
|---|---|---|
| Empty Bosnian content | `title_bs` blank causes empty string in API | Serializer falls back to `_en` value when `_bs` is blank |
| `alt_text_bs` empty | Accessibility fails for Bosnian visitors if alt text missing | Fallback to `_en` ensures non-empty alt text in all cases; content entry is admin responsibility |
| SEO fields without Bosnian content | Search engines get English SEO for Bosnian pages | Fallback covers this until Bosnian SEO is authored |
| Frontend doing translation logic | Frontend reads `title_en`/`title_bs` and chooses | **Anti-pattern.** API must never expose `_en`/`_bs` fields on public endpoints. Serializers must resolve and return canonical names only. |
| `?lang=` param forgotten on some endpoints | Some responses come back in wrong language | All four views must apply the same `lang` resolution. Centralise in a mixin or utility function. |
| Original columns dropped too early | Data lost before `_en` fields are populated | Data migration (step 2) must be verified before step 5. Both migrations in sequence, not combined. |
| `django-modeltranslation` introduced later | Conflicts with explicit `_en`/`_bs` columns | Do not install `django-modeltranslation`. It manages its own column naming convention and will conflict. The explicit column approach is self-contained. |
| Language parameter injection | Malicious `?lang=<script>` input | Resolved by whitelist: only `'en'` and `'bs'` are accepted; anything else falls back to `'en'`. No user input is reflected into SQL or templates. |
| `tags` accidentally bilingual | Developer stores per-language tags without a decision | Defer explicitly. Keep `tags` as flat list until the requirement is confirmed. |

---

## 11. Proposed Implementation Order

Steps are ordered for safety, reversibility, and incremental verification. No step modifies existing API behaviour until serializers are updated in step 5.

```
1.  Add _en / _bs fields to Album and MediaItem in gallery/models.py.
    All new fields: blank=True (non-breaking addition).

2.  Run makemigrations — confirm one new migration generated for gallery.

3.  Run migrate.

4.  Write and run a data migration that copies existing field values into _en fields:
      Album: title → title_en, description → description_en,
             seo_title → seo_title_en, seo_description → seo_description_en
      MediaItem: title → title_en, description → description_en,
                 alt_text → alt_text_en, caption → caption_en
    Verify: Album.objects.filter(title_en='').count() == 0 (assuming no blank titles exist)

5.  Update gallery/serializers.py:
      - Add a helper that resolves lang: get_lang(context) → 'en' | 'bs'
      - Replace ModelSerializer direct field reads with SerializerMethodField for all
        bilingual fields (title, description, alt_text, caption, seo_title, seo_description)
      - Each method: getattr(obj, f'{field}_{lang}') or getattr(obj, f'{field}_en')

6.  Update gallery/views.py:
      - Add get_serializer_context() override to all four views
      - Resolve lang from request.query_params.get('lang', 'en')
      - Whitelist: lang if lang in ('en', 'bs') else 'en'
      - Pass lang into serializer context

7.  Validate API responses:
      - Confirm ?lang=en returns English values
      - Confirm ?lang=bs returns Bosnian values (blank for now — falls back to English)
      - Confirm no ?lang= returns English
      - Confirm ?lang=fr returns English (fallback)

8.  Update gallery/admin.py:
      - Add fieldsets to AlbumAdmin grouping English and Bosnian content sections
      - Add fieldsets to MediaItemAdmin grouping English and Bosnian content sections
      - Remove original title, description, etc. from list_display/search_fields
        and replace with _en equivalents

9.  Verify Django admin:
      - Confirm existing record English content appears in _en fields
      - Enter sample Bosnian content
      - Confirm API ?lang=bs returns Bosnian content

10. Drop original title, description, alt_text, caption, seo_title, seo_description
    columns from Album and MediaItem in a separate migration.
    Run only after step 9 is verified.

11. Run python manage.py check — confirm zero errors or warnings.
```

---

## 12. Summary

| Topic | Decision |
|---|---|
| Model strategy | Option A — explicit `_en` / `_bs` column pairs |
| API language selection | `?lang=` query parameter, default `en`, invalid → `en` |
| Fallback within record | `_bs` blank → fall back to `_en` silently |
| Serializer output | Canonical field names only (`title`, not `title_en`) |
| Admin | Standard fieldsets grouping EN and BS content; no custom dashboard |
| Tags | Language-neutral for MVP; decision deferred |
| Packages | None required |
| Frontend | Pass `?lang=${currentLanguage}`; read canonical field names |
| Original columns | Coexist during migration window; dropped after data migration verified |

**No code changed.**
