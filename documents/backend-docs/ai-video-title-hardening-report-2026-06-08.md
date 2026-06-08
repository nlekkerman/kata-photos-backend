# Backend: Harden AI Video Title Generation — Hardening Report

**Date:** 2026-06-08  
**Scope:** Backend only (`kata-photos-backend`)  
**Full test suite:** Intentionally skipped per spec. Targeted tests only.

---

## Summary

Post-implementation hardening pass on the AI video title generation feature. Three factual correctness issues were investigated: legacy endpoint status, `original_filename` availability, and AI title length enforcement. One code change was made (title length cap). One issue requires a follow-up deletion task (legacy view). One non-issue was confirmed and documented (`original_filename`).

---

## Files Changed

| File | Change |
|---|---|
| `gallery/services/video_titles.py` | Added `_TITLE_MAX_LEN = 120` constant; applied hard cap in `generate_video_title_bs_from_description` |
| `gallery/tests/test_video_title_generation.py` | Added `test_long_ai_title_is_capped` (1 new test, 20 total) |

---

## Finding 1 — Legacy `VideoClipDirectUploadView`

### Status: **Flagged for deletion — NOT removed in this task**

`VideoClipDirectUploadView` is registered at:

```
POST /api/gallery/videos/direct-upload/   →   VideoClipDirectUploadView
```

The admin-canonical equivalent is:

```
POST /api/gallery/admin/videos/direct-upload/   →   AdminVideoDirectUploadView
```

The prior audit (`backend-full-audit-heroku-readiness-2026-06-03.md`, line 155) explicitly flags this as "superseded by admin-prefixed equivalents" and marks it for investigation — but does **not** confirm that no frontend currently calls it.

**Why not removed here:**
- Removal requires changes to both `gallery/urls.py` and `gallery/views.py`.
- The `VideoClipDirectUploadRequestSerializer` in `serializers.py` is exclusively used by this view and would need to be removed too.
- Without confirmed frontend data, removing a registered route risks breaking an active consumer.

**Follow-up deletion plan (separate task):**
1. Confirm no active frontend/admin panel calls `POST /api/gallery/videos/direct-upload/`.
2. Remove `VideoClipDirectUploadView` class from `gallery/views.py`.
3. Remove `VideoClipDirectUploadView` import from `gallery/urls.py`.
4. Remove `path('videos/direct-upload/', ...)` from `gallery/urls.py`.
5. Remove `VideoClipDirectUploadRequestSerializer` from `gallery/serializers.py` (only used by this view).
6. Remove `VideoClipDirectUploadView` import from `gallery/views.py` imports in `gallery/urls.py`.

---

## Finding 2 — `original_filename` Not Available in Upload Views

### Status: **Confirmed unavailable — no code change needed**

In the Cloudflare Stream direct-upload flow, no file passes through Django. The browser uploads the video directly to Cloudflare's TUS endpoint after receiving the one-time URL. At the time `VideoClipDirectUploadView.post` or `AdminVideoDirectUploadView.post` executes, Django only receives:

```
album, title_bs, title_en, description_bs, description_en, max_duration_seconds
```

No filename is present in the request. Neither view passes `original_filename` to `resolve_video_titles`, which is correct. The `original_filename` parameter in `resolve_video_titles` defaults to `None` and the filename fallback is silently skipped. The parameter remains in the signature for potential future use at other call sites.

**No code change required.**

---

## Finding 3 — AI Title Length Cap

### Status: **Fixed**

`VideoClip.title_bs` has `max_length=255`. OpenAI is instructed to return 3–5 words, but the response is not validated server-side for length. A misbehaving model could return a sentence-length string.

**Change made** in `gallery/services/video_titles.py`:

```python
# Added constant
_TITLE_MAX_LEN = 120

# Applied in generate_video_title_bs_from_description, before returning:
return title.strip()[:_TITLE_MAX_LEN]
```

**Cap value rationale:**
- `120` is generous enough for any realistic `animal + location` pattern in Bosnian.
- Safely below the DB field limit of `255`.
- Python string slicing (`[:120]`) is Unicode-aware — it slices by code point, never splits multi-byte sequences, so Bosnian characters (`č ć ž š đ`) are never corrupted.
- Admin-provided `title_bs` is NOT capped — it is validated by the serializer (`max_length=255`) and reflects explicit admin intent. Silently truncating admin input would be incorrect behavior.

**Scope of cap:**
- Applies to: AI-generated titles only (return value of `generate_video_title_bs_from_description`).
- Does NOT apply to: admin-provided titles, or fallback paths (`_first_sentence_from_description` already caps at 60, `_clean_filename` at 80, timestamp is always short).

---

## Cloudflare `meta.name` Final Behavior

`meta={"name": title_bs}` is passed to `create_direct_upload` in both upload views.

`title_bs` at that point is:
- The admin-provided title (unchanged, serializer-validated) **or**
- The AI-generated title (capped at 120 chars) **or**
- A local fallback (first sentence ≤60 chars, filename ≤80 chars, or timestamp ~25 chars)

`resolve_video_titles` guarantees a non-blank string. `meta.name` is therefore always set and always non-blank.

---

## Validation

```
python manage.py check
→ System check identified no issues (0 silenced)

python manage.py test gallery.tests.test_video_title_generation --verbosity=2
→ Ran 20 tests in 0.919s — OK
```

---

## New Test Added

`test_long_ai_title_is_capped` in `GenerateTitleBsTests`:
- Constructs a Bosnian-character string of `_TITLE_MAX_LEN + 50` characters as the AI response.
- Asserts the return value is exactly `_TITLE_MAX_LEN` characters.
- Asserts Bosnian characters (`Č`) are not corrupted by the slice.

---

## Confirmations

- **Backend only** — no frontend changes, no public API contract changes.
- **Upload never fails if AI or translation fails** — no change to this guarantee; `resolve_video_titles` still never raises.
- **Full test suite intentionally skipped** — per spec; only the targeted test module was run.
