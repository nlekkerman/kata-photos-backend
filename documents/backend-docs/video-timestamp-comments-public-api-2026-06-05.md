# Video Timestamp Comments — Public API Implementation Report

**Date:** 2026-06-05

---

## Summary

Added a standalone public API for visitor-submitted timestamp comments on videos. Comments are submitted with `status=pending` and only become visible after admin approval. `author_email` is stored privately and is never exposed in any public response. `VisitorMessage` is unchanged.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/models.py` | Added `VideoTimestampComment` model |
| `gallery/serializers.py` | Added `VideoTimestampCommentCreateSerializer` and `VideoTimestampCommentPublicSerializer` |
| `gallery/views.py` | Added `VideoTimestampCommentListCreateView` |
| `gallery/public_urls.py` | Added route `videos/<int:video_pk>/comments/` |
| `gallery/admin.py` | Registered `VideoTimestampCommentAdmin` |
| `gallery/migrations/0013_video_timestamp_comment.py` | Auto-generated migration |

**Total: 6 files changed.**

---

## Model Added

**`gallery.VideoTimestampComment`** — `gallery/models.py`

### Fields

| Field | Type | Constraints |
|---|---|---|
| `video` | `ForeignKey(VideoClip)` | required, on_delete=CASCADE, related_name="timestamp_comments" |
| `author_name` | `CharField(max_length=120)` | required |
| `author_email` | `EmailField(max_length=254)` | required, private — never exposed in public API |
| `text` | `TextField` | required |
| `timestamp_seconds` | `PositiveIntegerField` | required, ≥ 0 |
| `status` | `CharField` choices: pending/approved/rejected | default=pending |
| `created_at` | `DateTimeField` | auto_now_add=True |
| `updated_at` | `DateTimeField` | auto_now=True |

### Status Choices

| Value | Label |
|---|---|
| `pending` | Pending |
| `approved` | Approved |
| `rejected` | Rejected |

### Meta

- `ordering = ['timestamp_seconds', 'created_at']`
- Indexes on `(video, status)`, `status`, `created_at`

---

## Endpoints Added

Both endpoints are under `api/public/` (mapped via `gallery/public_urls.py`).

### POST `/api/public/videos/<video_pk>/comments/`

Submit a new comment. Saved with `status=pending`. `author_email` is accepted but never returned.

**Request body:**

```json
{
  "author_name": "John",
  "author_email": "john@example.com",
  "text": "Amazing owl shot!",
  "timestamp_seconds": 17
}
```

**Response (201 Created):**

```json
{
  "id": 1,
  "author_name": "John",
  "text": "Amazing owl shot!",
  "timestamp_seconds": 17,
  "created_at": "2026-06-05T14:00:00Z"
}
```

### GET `/api/public/videos/<video_pk>/comments/`

Returns only `approved` comments for the given video, ordered by `timestamp_seconds` then `created_at`.

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "author_name": "John",
    "text": "Amazing owl shot!",
    "timestamp_seconds": 17,
    "created_at": "2026-06-05T14:00:00Z"
  }
]
```

`author_email` is never present in any public response.

---

## Serializers Added

### `VideoTimestampCommentCreateSerializer`

- Fields: `id`, `author_name`, `author_email` (write-only), `text`, `timestamp_seconds`, `created_at`
- `author_email` is `write_only=True` — accepted on input, excluded from output
- `timestamp_seconds` validated with `min_value=0`
- `status` is not in the serializer fields; set server-side to `pending`

### `VideoTimestampCommentPublicSerializer`

- Fields: `id`, `author_name`, `text`, `timestamp_seconds`, `created_at`
- Read-only; `author_email` is intentionally absent

---

## Admin Moderation Behavior

**`VideoTimestampCommentAdmin`** — `gallery/admin.py`

- `list_display`: `video`, `author_name`, `text_preview`, `timestamp_seconds`, `status`, `created_at`
- `list_filter`: `status`, `video`, `created_at`
- `search_fields`: `author_name`, `author_email`, `text`
- `ordering`: `-created_at`
- `readonly_fields`: `author_email`, `created_at`, `updated_at` (email visible in admin detail but not editable)
- `text_preview` helper: first 50 characters of `text` followed by `…` if longer

Fieldsets: Comment (video, timestamp_seconds, author_name, author_email, text), Moderation (status), Timestamps.

Admin workflow:
1. New submissions arrive with `status=pending`.
2. Admin opens the record, reviews content, and sets `status` to `approved` or `rejected`.
3. Only `approved` comments appear in the public GET endpoint.

---

## Migration Created

```
gallery/migrations/0013_video_timestamp_comment.py
```

Command used:

```
python manage.py makemigrations gallery --name video_timestamp_comment
```

Operations applied:
- Create model `VideoTimestampComment`

---

## Commands Run

```
python manage.py makemigrations gallery --name video_timestamp_comment
python manage.py check
python manage.py test gallery --verbosity=1
```

---

## Test Results

```
System check identified no issues (0 silenced).
Ran 110 tests in 48.751s
OK
```

All pre-existing tests pass. No new tests were added (consistent with project pattern).

---

## What Was Intentionally Not Implemented

- Email notifications to admin on new comment submission
- Auto-approval of comments
- Reply functionality
- Likes or reactions
- Rate limiting or CAPTCHA
- Listing or retrieval endpoint for a single comment by ID
- Frontend changes
- Any modification to `VisitorMessage`
- Merging comments with private visitor messages
