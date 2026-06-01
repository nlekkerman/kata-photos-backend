# Gallery Upload Safety — Phase 6 Implementation Report

**Date:** 2026-06-01  
**Phase:** 6 — Backend upload safety hardening  
**Status:** Complete

---

## Files Changed

| File | Change |
|---|---|
| `gallery/serializers.py` | Added upload constants and `validate_original_file` method; added orphan-file comment |
| `gallery/tests.py` | Added `UploadSafetyTests` class (8 new tests) |

Total files changed: 2

---

## Validation Rules Added

### `gallery/serializers.py` — `MediaItemWriteSerializer.validate_original_file`

A new field-level validator is called by DRF automatically whenever `original_file` is present in the request.

1. **Size check** — `file.size > MAX_IMAGE_UPLOAD_SIZE_MB * 1024 * 1024`  
   Rejects with: `"Image file too large. Maximum allowed size is 10 MB."`

2. **Content-type check** — `content_type not in ALLOWED_IMAGE_CONTENT_TYPES`  
   Rejects with: `"Unsupported file type '<type>'. Allowed types: image/jpeg, image/png, image/webp."`  
   Uses `not content_type` to also reject `None` (e.g., unknown Pillow format with no registered MIME).

Both return a standard DRF `400 Bad Request` with `{ "original_file": ["..."] }`.

---

## Max Upload Size

```python
MAX_IMAGE_UPLOAD_SIZE_MB = 10
```

Limit: **10 MB** per upload.

---

## Allowed Content Types

```python
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
```

**Important implementation note:** Django's `forms.ImageField.to_python` (used internally by DRF's `ImageField`) always overwrites `file.content_type` with `Image.MIME.get(image.format)` — the Pillow-detected MIME type — regardless of what the browser sent. This means validation is based on the **actual image format** (reliable), not the client-supplied Content-Type header (unreliable). Accepted by this validator: JPEG, PNG, WEBP. Rejected: GIF, BMP, TIFF, PPM, and any format for which Pillow has no registered MIME type (`None`).

---

## Serializer Behavior

### `original_file` — field-level (`validate_original_file`)

| Condition | Result |
|---|---|
| File > 10 MB | `400` — `original_file`: size error |
| Content-type not in allowed set | `400` — `original_file`: type error |
| Content-type is `None` | `400` — `original_file`: type error |
| Not a valid image (no Pillow support) | `400` — `original_file`: DRF ImageField error (before our validator) |
| Unknown file extension (e.g., `.bin`) | `400` — `original_file`: DRF ImageField extension error (before our validator) |

### `original_file` — object-level (`validate`)

| Condition | Result |
|---|---|
| Create with no `original_file` | `400` — `original_file`: "An image file is required." |

### `is_published` / `alt_text_bs`

| Condition | Result |
|---|---|
| `is_published=True`, `alt_text_bs` missing | `400` — `alt_text_bs`: required |

### English fields

All optional. No automatic translation. No fake English.

---

## File Replacement (PATCH) — Orphan Risk

A code comment was added in `validate()`:

```python
# NOTE: Replacing original_file on PATCH leaves the previous file on disk.
# Orphaned file cleanup should be handled in a future cleanup phase
# (e.g., a pre_save signal or a periodic management command).
```

No cleanup logic was added in this phase.

---

## Tests Added

New class: `UploadSafetyTests` in `gallery/tests.py`

| Test | What it verifies |
|---|---|
| `test_valid_jpeg_upload_accepted` | Staff can upload a valid JPEG → 201 |
| `test_valid_png_upload_accepted` | Staff can upload a valid PNG → 201 |
| `test_valid_webp_upload_accepted` | Staff can upload a valid WEBP → 201 (skips if Pillow has no WEBP support) |
| `test_oversized_upload_rejected` | 11 MB JPEG (valid header + null-byte padding) → 400 with `original_file` key |
| `test_unsupported_content_type_rejected` | Actual GIF image → 400 with `original_file` key |
| `test_missing_content_type_rejected` | JPEG with `.bin` extension and `application/octet-stream` → 400 (rejected by DRF ImageField extension check) with `original_file` key |
| `test_published_without_alt_text_bs_rejected` | `is_published=True`, no `alt_text_bs` → 400 |
| `test_public_media_list_still_works` | Published media visible, unpublished hidden |

**Oversized test approach:** A small valid JPEG is created and padded with null bytes to 11 MB. Pillow ignores trailing bytes after the JPEG EOI marker, so DRF's `ImageField` accepts the file. The actual `file.size` received by the server equals the full 11 MB content length, which triggers our size validator.

**Unsupported type test approach:** Sends an actual GIF image (not a mislabelled JPEG). Django's `ImageField.to_python` normalises `content_type` to the Pillow-detected MIME type, so only genuine GIF/BMP/TIFF etc. files carry a non-allowed content_type into `validate_original_file`.

All test files are generated in-memory using `PIL.Image.new` and `SimpleUploadedFile`. No fixture files committed.

---

## Commands Run

```
python manage.py makemigrations --check --dry-run  →  No changes detected (exit 0)
python manage.py migrate                           →  No migrations to apply (exit 0)
python manage.py check                             →  No issues (exit 0)
python manage.py test --verbosity=2                →  Ran 35 tests in ~31s — OK (exit 0)
```

---

## Validation Results

**35/35 tests passed.**

```
Ran 35 tests in 30.886s
OK
```

All 8 new `UploadSafetyTests` pass. All pre-existing `AlbumWriteAPITests`, `MediaUploadAPITests`, and `AlbumCoverAPITests` continue to pass.

---

## Confirmations

| Constraint | Status |
|---|---|
| No frontend files touched | ✓ Confirmed |
| No Cloudinary or Cloudflare logic added | ✓ Confirmed |
| No thumbnail generation added | ✓ Confirmed |
| No translation logic added | ✓ Confirmed |
| No JWT / token auth added | ✓ Confirmed |
| No fake English | ✓ Confirmed |
| No dummy data | ✓ Confirmed |
| Public API contracts unchanged | ✓ Confirmed |
| Existing tests still pass | ✓ Confirmed |

---

## Follow-up Risks / Notes

### Orphaned files on PATCH

When `original_file` is replaced via `PATCH /api/gallery/media/<id>/`, the old file remains on disk. Django's `ImageField` does not automatically delete the previous file when the field value changes. This should be addressed in a future cleanup phase — options include:

- A `pre_save` signal on `MediaItem` that deletes the old file before overwrite.
- A periodic management command that scans `media/` for files not referenced by any `MediaItem`.
- Cloudinary (future): file lifecycle managed by the provider.

### Content-type normalisation

Django's `ImageField.to_python` sets `file.content_type = Image.MIME.get(image.format)` before the DRF field-level validator runs. Validation is therefore based on the actual Pillow-detected format, not the browser-supplied Content-Type. This is more secure (can't be spoofed) but means there is no separate "content_type header" check — format and content_type are the same source of truth.

### No video upload validation

Video files are not handled by this phase. `media_type="image"` is enforced implicitly by `ImageField`. Future video upload support will require its own validation path.

### Pillow WEBP support

WEBP support depends on the Pillow build (requires `libwebp`). The WEBP test skips gracefully if the codec is unavailable. The local environment supports WEBP and the test passes.
