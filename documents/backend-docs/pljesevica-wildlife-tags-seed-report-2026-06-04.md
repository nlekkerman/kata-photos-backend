# Plješevica Wildlife Tags Seed Report — 2026-06-04

## Summary

A Django management command has been added to seed an initial curated set of Plješevica / Una / Dinaric wildlife tags. The command is safe to run multiple times: existing tags are always skipped by slug, never overwritten or deleted. A `--dry-run` flag is supported. All 78 tests pass (70 pre-existing + 8 new).

---

## Files Changed

| File | Type of Change |
|------|---------------|
| `gallery/management/__init__.py` | New (empty Django package init) |
| `gallery/management/commands/__init__.py` | New (empty Django package init) |
| `gallery/management/commands/seed_pljesevica_wildlife_tags.py` | New management command |
| `gallery/tests.py` | Added `from django.core.management import call_command` import; added `SeedWildlifeTagsCommandTests` class (8 new tests) |

Total: 4 files (3 new, 1 modified). No migrations created.

---

## Command Added

```
gallery/management/commands/seed_pljesevica_wildlife_tags.py
```

Runnable with:

```bash
python manage.py seed_pljesevica_wildlife_tags
python manage.py seed_pljesevica_wildlife_tags --dry-run
```

---

## Seed Categories Included

| Category | Count |
|----------|-------|
| Broad animal groups | 13 |
| Large mammals / iconic regional wildlife | 16 |
| Birds and bird groups | 18 |
| Reptiles and amphibians | 10 |
| River / fish wildlife | 6 |
| Insects / butterflies / small wildlife | 8 |
| Habitat / observation tags | 13 |
| **Total** | **84** |

---

## Number of Tags in Seed List

**84 tags.**

---

## Dry-Run Implemented

Yes. `--dry-run` flag is supported.

```bash
python manage.py seed_pljesevica_wildlife_tags --dry-run
```

Dry-run prints `[create]` or `[skip]` for each entry and reports "Would create X, would skip Y" without writing anything to the database.

---

## Duplicate / Skipping Behaviour

| Scenario | Behaviour |
|----------|-----------|
| Tag already exists by `slug` | Skipped via `get_or_create(slug=slug, defaults=...)` — existing record is untouched |
| `name_en` was edited by an admin | Not overwritten — `defaults=` is only applied on creation |
| Command run twice | Second run prints "Created 0, skipped 84 (total processed: 84)" |
| Duplicate slug within seed list | Detected via an in-memory `seen_slugs` set; logged as WARNING and skipped |
| Empty database | All 84 tags created on first run |

Slug generation uses `django.utils.text.slugify(name_bs)`, matching the behaviour of `Tag.save()`. Bosnian diacritics (`š`, `ć`, `č`, `ž`, `đ`) are transliterated to their ASCII base characters (e.g. `"Šuma"` → `"suma"`, `"Smeđi medvjed"` → `"smei-medvjed"`).

---

## Tests Added

8 new tests in a new class `SeedWildlifeTagsCommandTests` in `gallery/tests.py`:

| Test | What is covered |
|------|----------------|
| `test_command_creates_all_seed_tags` | 84 Tag rows created in a clean DB |
| `test_command_output_reports_correct_created_count` | Output contains "Created 84" and "skipped 0" |
| `test_command_idempotent_on_rerun` | Running twice still yields exactly 84 tags (no duplicates) |
| `test_second_run_reports_all_skipped` | Output on second run contains "Created 0" and "skipped 84" |
| `test_existing_tag_by_slug_is_not_duplicated` | Pre-created "ptice" tag remains a single row after seeding |
| `test_existing_edited_name_en_is_not_overwritten` | Pre-created tag with custom `name_en` is unchanged after seeding |
| `test_dry_run_does_not_create_tags` | Dry-run writes zero rows to the database |
| `test_dry_run_output_reports_would_create` | Dry-run output contains "Would create 84" and "would skip 0" |

---

## Commands Run

```bash
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test gallery --verbosity=2
.\.venv\Scripts\python.exe manage.py seed_pljesevica_wildlife_tags --dry-run
.\.venv\Scripts\python.exe manage.py seed_pljesevica_wildlife_tags
.\.venv\Scripts\python.exe manage.py seed_pljesevica_wildlife_tags
```

---

## Validation Results

```
manage.py check      → System check identified no issues (0 silenced)
manage.py test gallery → Ran 78 tests in ~50s    OK
```

All 78 tests pass (70 pre-existing + 8 new).

Manual seed run 1:  Created 84, skipped 0  (total processed: 84)
Manual seed run 2:  Created 0,  skipped 84 (total processed: 84)
Dry-run:            Would create 84, would skip 0 (total processed: 84)

---

## Confirmation: Frontend Files Not Touched

No frontend files were modified. Changes are limited to:

- `gallery/management/__init__.py`
- `gallery/management/commands/__init__.py`
- `gallery/management/commands/seed_pljesevica_wildlife_tags.py`
- `gallery/tests.py`

---

## Confirmation: No Migrations Created

No migrations were created or required. The `Tag` model and its table already exist from migration `0010_tags_and_m2m`. This command only inserts rows using `Tag.objects.get_or_create()`.

---

## Known Limitations / Follow-up Tasks

| Limitation | Notes |
|-----------|-------|
| Slug `smei-medvjed` for "Smeđi medvjed" | Django's `slugify` drops the `đ` combining character, leaving `smei`. This is consistent with how `Tag.save()` would auto-generate slugs. The slug is stable and unique. A custom slugify (e.g. `python-slugify` with Bosnian transliteration) could produce `smedi-medvjed` if desired. |
| No category grouping on `Tag` model | The seed categories exist only in code comments. If admins need visible grouping, a `category` field on `Tag` could be added as a follow-up. |
| No public `/api/public/tags/` listing endpoint | Not in scope; can be added if the frontend needs a standalone tag browser. |
| Single `?tag=<slug>` filter only | Multi-tag AND/OR filtering can be added as a follow-up to `AlbumListCreateView` and `VideoClipListView`. |
| Seed list is curated, not exhaustive | More species can be added to `SEED_TAGS` in future phases without migrations or model changes. |
