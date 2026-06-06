# Backend Admin Comments and Messages Endpoints

**Date:** 2026-06-06  
**Scope:** New admin list and moderation endpoints for visitor messages and video timestamp comments  
**Status:** Implemented — `manage.py check` passing

---

## Files Changed

| File | Change type |
|---|---|
| `gallery/views_admin_messages.py` | **Created** — new focused view module |
| `gallery/serializers.py` | 3 new serializers added |
| `gallery/urls.py` | Imports from new module added; 3 new routes added |

No other files were touched. No frontend files were touched. No automated tests were run.

---

## New View Module

`gallery/views_admin_messages.py` (~100 lines) contains:

- `AdminMessagePageNumberPagination` — shared pagination (page_size=50, max=200)
- `AdminVisitorMessageListView` — GET list
- `AdminVideoTimestampCommentListView` — GET list
- `AdminVideoTimestampCommentDetailView` — PATCH status update

---

## New Endpoints

### 1. `GET /api/gallery/admin/visitor-messages/`

| Property | Value |
|---|---|
| Permission | `IsAdminUser` (staff only) |
| Pagination | PageNumber, default 50, max 200 |
| Filter | `?status=new\|read\|replied\|archived` (optional) |
| Ordering | Newest first (`-created_at`, model default) |

**Response shape (per item):**
```json
{
  "id": 1,
  "sender_name": "Ana Kovač",
  "sender_email": "ana@example.com",
  "subject": "Inquiry",
  "message": "Hello...",
  "status": "new",
  "video_id": null,
  "timestamp_seconds": null,
  "created_at": "2026-06-06T10:00:00Z",
  "replied_at": null
}
```

---

### 2. `GET /api/gallery/admin/video-timestamp-comments/`

| Property | Value |
|---|---|
| Permission | `IsAdminUser` (staff only) |
| Pagination | PageNumber, default 50, max 200 |
| Filter | `?status=pending\|approved\|rejected` (optional) |
| Ordering | Newest first (`-created_at`) |

**Response shape (per item):**
```json
{
  "id": 7,
  "video_id": 3,
  "video_title_bs": "Planinska magla",
  "author_name": "Marko",
  "author_email": "marko@example.com",
  "text": "Lijepa scena!",
  "timestamp_seconds": 42,
  "status": "pending",
  "created_at": "2026-06-06T09:30:00Z"
}
```

---

### 3. `PATCH /api/gallery/admin/video-timestamp-comments/<pk>/`

| Property | Value |
|---|---|
| Permission | `IsAdminUser` (staff only) |
| Accepted methods | PATCH only |
| Writable field | `status` only |
| Allowed status values | `pending`, `approved`, `rejected` |

**Request body:**
```json
{ "status": "approved" }
```

**Response:** Full admin comment object (same shape as list item above).

**Validation error example (invalid status):**
```json
{ "status": ["Invalid status. Allowed values: approved, pending, rejected."] }
```

---

## New Serializers (in `gallery/serializers.py`)

| Serializer | Purpose |
|---|---|
| `AdminVisitorMessageSerializer` | Read-only, staff-facing, exposes `sender_email` |
| `AdminVideoTimestampCommentSerializer` | Read-only, staff-facing, exposes `author_email` and `video_title_bs` |
| `AdminVideoTimestampCommentStatusSerializer` | Write serializer for PATCH — only `status` field, with validation |

---

## Updated `gallery/urls.py`

Imports added from `views_admin_messages`:
```python
from .views_admin_messages import (
    AdminVideoTimestampCommentDetailView,
    AdminVideoTimestampCommentListView,
    AdminVisitorMessageListView,
)
```

Routes added under the existing admin section:
```python
path('admin/visitor-messages/', AdminVisitorMessageListView.as_view(), name='admin-visitor-message-list'),
path('admin/visitor-messages/<int:pk>/reply/', VisitorMessageReplyView.as_view(), name='admin-visitor-message-reply'),
path('admin/video-timestamp-comments/', AdminVideoTimestampCommentListView.as_view(), name='admin-video-timestamp-comment-list'),
path('admin/video-timestamp-comments/<int:pk>/', AdminVideoTimestampCommentDetailView.as_view(), name='admin-video-timestamp-comment-detail'),
```

The existing `admin-visitor-message-reply` route is preserved unchanged.

---

## Public/Private System Separation

| System | Model | Admin endpoint | Public endpoint | `author_email` exposed publicly? |
|---|---|---|---|---|
| Video timestamp comments | `VideoTimestampComment` | `/admin/video-timestamp-comments/` | `/api/public/videos/<pk>/comments/` | **No** (`VideoTimestampCommentPublicSerializer` excludes it) |
| Visitor messages | `VisitorMessage` | `/admin/visitor-messages/` | POST `/api/public/messages/` (write-only) | N/A — never readable publicly |

The two systems remain fully separate. No merging was performed.

---

## `manage.py check` Result

```
System check identified no issues (0 silenced).
```

---

## Manual Verification Checklist

1. Login as staff/admin locally.
2. `GET /api/gallery/admin/visitor-messages/` — confirm 200 with paginated list (or empty `results: []`).
3. `GET /api/gallery/admin/visitor-messages/?status=new` — confirm filter works.
4. `GET /api/gallery/admin/video-timestamp-comments/` — confirm 200 with paginated list.
5. `GET /api/gallery/admin/video-timestamp-comments/?status=pending` — confirm only pending comments returned.
6. `PATCH /api/gallery/admin/video-timestamp-comments/<pk>/` with `{"status": "approved"}` — confirm 200 and updated status in response.
7. `PATCH /api/gallery/admin/video-timestamp-comments/<pk>/` with `{"status": "rejected"}` — confirm 200.
8. `PATCH /api/gallery/admin/video-timestamp-comments/<pk>/` with `{"status": "pending"}` — confirm 200.
9. `GET /api/public/videos/<pk>/comments/` — confirm only approved comments appear.
10. Verify anonymous access to `/admin/visitor-messages/` returns 401/403 (not 200).
11. Verify anonymous access to `/admin/video-timestamp-comments/` returns 401/403.
12. Verify `GET /api/public/videos/<pk>/comments/` does not expose `author_email`.

---

## What Was Intentionally Not Implemented

| Item | Reason |
|---|---|
| Automated tests | Explicitly excluded per task constraints |
| `author_email` in public comment endpoint | Already excluded in `VideoTimestampCommentPublicSerializer`; not changed |
| Status update for `VisitorMessage` (mark as read/archived) | Not requested; reply endpoint already exists |
| Comment reply/email functionality | Not requested for comments |
| Chat, likes, reactions, user accounts | Explicitly out of scope |
| Refactoring existing `gallery/views.py` | Not required; new module created instead |
| Pagination on the PATCH detail endpoint | Not applicable to a single-object update |
| GET single visitor message detail | Not requested |
