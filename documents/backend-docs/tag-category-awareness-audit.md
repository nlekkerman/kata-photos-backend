# Tag Category Awareness Audit

**Date:** 2026-06-09  
**Auditor:** GitHub Copilot  
**Purpose:** Pre-implementation audit before writing a location tag seed command.

---

## Files Inspected

| File | Relevance |
|---|---|
| `gallery/models.py` | Tag model definition |
| `gallery/serializers.py` | TagSerializer, TagWriteSerializer |
| `gallery/views.py` | AdminTagListCreateView, AdminTagRetrieveUpdateDestroyView |
| `gallery/admin.py` | Django admin registration for Tag |
| `gallery/urls.py` | API URL routing for tag endpoints |
| `gallery/migrations/0010_tags_and_m2m.py` | Initial Tag model (no category) |
| `gallery/migrations/0020_tag_seo_fields_mediaitem_tags_m2m.py` | Added category, description_bs, description_en |
| `gallery/management/commands/seed_pljesevica_wildlife_tags.py` | Existing wildlife tag seed (no category) |
| `gallery/management/commands/seed_seo_tags.py` | Existing SEO tag seed (uses category) |

---

## Current Tag Model Shape

```python
class Tag(models.Model):
    CATEGORY_LOCATION    = 'location'
    CATEGORY_SPECIES     = 'species'
    CATEGORY_HABITAT     = 'habitat'
    CATEGORY_BEHAVIOR    = 'behavior'
    CATEGORY_CONTENT_TYPE = 'content_type'
    CATEGORY_GENERAL     = 'general'

    CATEGORY_CHOICES = [
        ('location',     'Location'),
        ('species',      'Species'),
        ('habitat',      'Habitat'),
        ('behavior',     'Behavior'),
        ('content_type', 'Content Type'),
        ('general',      'General'),
    ]

    name_bs      = CharField(max_length=100)           # required, Bosnian name
    name_en      = CharField(max_length=100, blank=True)
    slug         = SlugField(max_length=120, unique=True)  # dedup key
    category     = CharField(choices=CATEGORY_CHOICES, default='general', db_index=True)
    description_bs = TextField(blank=True)
    description_en = TextField(blank=True)
    created_at   = DateTimeField(auto_now_add=True)
    updated_at   = DateTimeField(auto_now=True)
```

- Slug is auto-generated from `name_bs` on first save if blank.
- Default `category` is `'general'`.
- `ordering = ['slug']`.

---

## Answers to Audit Questions

**1. Does the `Tag` model already have a category field?**  
Yes. `category` is a `CharField` with six hard-coded choices defined directly on the model class.

**2. How are categories stored?**  
Simple string choices on the `Tag` table itself (`CharField(max_length=40, choices=..., db_index=True)`). No separate `Category` model or FK. Values are plain slugs: `location`, `species`, `habitat`, `behavior`, `content_type`, `general`.

**3. Are tag categories already exposed through the API?**  
Yes, fully. `TagSerializer` and `TagWriteSerializer` both include `category` in their `fields` list. The admin endpoints `GET /api/gallery/admin/tags/` and `PATCH /api/gallery/admin/tags/<pk>/` read and write `category`.

**4. Are existing tags already grouped into categories?**  
Partially. The 84 wildlife tags seeded by `seed_pljesevica_wildlife_tags` were created without a category field (migration 0020 arrived later) and therefore all default to `'general'`. The 17 SEO tags added by `seed_seo_tags` are correctly categorised (`location`, `species`, `habitat`, `behavior`). No tags in the current seed corpus use `content_type`.

**5. What category value should location tags use?**  
`Tag.CATEGORY_LOCATION` → string value `'location'`. This is already used by `seed_seo_tags` for Bosna i Hercegovina, Bihać, Plješevica, Una National Park, Rijeka Una, and Greben.

**6. Would adding the seed command require a migration?**  
No. The `category` field, `description_bs`, and `description_en` columns already exist (added in migration `0020`). The new command only reads and writes data; no schema change is needed.

**7. Are bilingual fields already present on tags?**  
Yes. Both `name_bs` and `name_en` have existed since migration `0010`. `description_bs` and `description_en` were added in `0020`. All four fields are present and writable.

**8. What is the safest duplicate-prevention key?**  
`slug` (unique constraint, `db_index=True`). Both existing seed commands use slug as the dedup key. `seed_seo_tags` uses `update_or_create(slug=slug, ...)` which is the correct pattern. `seed_pljesevica_wildlife_tags` computes the slug from `name_bs` and skips if the slug already exists.

---

## Current API / Serializer Support

| Endpoint | Auth | Category field |
|---|---|---|
| `GET  /api/gallery/admin/tags/` | IsAdminUser | Returned in response |
| `POST /api/gallery/admin/tags/` | IsAdminUser | Accepted in request |
| `GET  /api/gallery/admin/tags/<pk>/` | IsAdminUser | Returned in response |
| `PATCH /api/gallery/admin/tags/<pk>/` | IsAdminUser | Accepted in request |
| `DELETE /api/gallery/admin/tags/<pk>/` | IsAdminUser | N/A |

There is **no public tag list endpoint** (e.g. `GET /api/gallery/tags/`). Tags are only exposed as embedded arrays on albums/videos via their respective public serializers.

---

## Risks / Unknowns

- **`seed_pljesevica_wildlife_tags` tags are uncategorised.** All 84 wildlife tags created by that command have `category='general'` because the category field did not exist at seed time and the command never sets it. A future follow-up could backfill these, but that is out of scope for the location seed.
- **Django admin `TagAdmin` does not expose `category` in `list_display` or `list_filter`.** This is a minor admin UX gap but does not affect the seed command.
- **No public tag-by-category filtering endpoint exists.** If the frontend needs to fetch only `location` tags for a map/filter widget, that endpoint does not yet exist. The admin endpoint supports `queryset = Tag.objects.all()` with no filtering; a `?category=` filter would need to be added if required.
- **`seed_seo_tags` already covers the most obvious location slugs** (`bosna-i-hercegovina`, `bihac`, `pljesevica`, `una-national-park`, `rijeka-una`, `greben`). The location seed command must check for slug conflicts and either skip or extend those entries rather than duplicate them.

---

## Recommendation for Next Implementation Prompt

The location tag seed command can be implemented immediately with no migration.

Use `update_or_create(defaults={...}, slug=slug)` as the write pattern — identical to `seed_seo_tags`. Set `category=Tag.CATEGORY_LOCATION` on every entry. Provide both `name_bs` and `name_en`, and optionally `description_bs` / `description_en`.

Suggested command name: `seed_location_tags`  
Suggested file: `gallery/management/commands/seed_location_tags.py`

Avoid re-seeding slugs already covered by `seed_seo_tags` unless intentionally expanding their descriptions. The six slugs already present (`bosna-i-hercegovina`, `bihac`, `pljesevica`, `una-national-park`, `rijeka-una`, `greben`) will be safely updated if included because `update_or_create` is idempotent.
