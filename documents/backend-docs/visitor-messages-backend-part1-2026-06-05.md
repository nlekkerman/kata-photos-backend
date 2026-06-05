# Visitor Messages Backend — Part 1 Implementation Report

**Date:** 2026-06-05

---

## Summary

Implemented the first backend layer for private visitor contact messages. Visitors can now `POST` a message via a public API endpoint. Messages are persisted to the database and fully manageable through Django admin.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/models.py` | Added `VisitorMessage` model |
| `gallery/serializers.py` | Added `VisitorMessageCreateSerializer` |
| `gallery/views.py` | Added `VisitorMessageCreateView` |
| `gallery/public_urls.py` | Registered `POST /api/public/messages/` route |
| `gallery/admin.py` | Registered `VisitorMessageAdmin` |
| `gallery/migrations/0011_visitor_message.py` | Auto-generated migration |

**Total: 6 files changed.**

---

## Model Added

**`gallery.VisitorMessage`** — `gallery/models.py`

| Field | Type | Constraints |
|---|---|---|
| `sender_name` | `CharField` | max_length=120, required |
| `sender_email` | `EmailField` | max_length=254, required |
| `subject` | `CharField` | max_length=180, required |
| `message` | `TextField` | required |
| `status` | `CharField` | choices: new / read / replied / archived, default=new |
| `created_at` | `DateTimeField` | auto_now_add=True |
| `updated_at` | `DateTimeField` | auto_now=True |

Default ordering: `-created_at`.

---

## Serializer Added

**`VisitorMessageCreateSerializer`** — `gallery/serializers.py`

- Write serializer only (used for `POST` submission).
- Public response fields: `id`, `sender_name`, `sender_email`, `subject`, `message`, `created_at`.
- `status` and `updated_at` are **not** exposed in the response.
- Validates and trims whitespace from `sender_name`, `subject`, and `message`.
- `sender_email` validated as a valid email address by DRF's `EmailField`.

---

## Endpoint Added

**`POST /api/public/messages/`**

- **Permission:** `AllowAny` — fully public, no authentication required.
- **Method:** `POST` only (write-only for visitors — no list, no retrieve).
- **Request body:**
  ```json
  {
    "sender_name": "John Doe",
    "sender_email": "john@example.com",
    "subject": "Question about wildlife photos",
    "message": "Hello, I wanted to ask..."
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": 1,
    "sender_name": "John Doe",
    "sender_email": "john@example.com",
    "subject": "Question about wildlife photos",
    "message": "Hello, I wanted to ask...",
    "created_at": "2026-06-05T12:00:00Z"
  }
  ```

---

## Admin Registration

**`VisitorMessageAdmin`** — `gallery/admin.py`

- `list_display`: sender_name, sender_email, subject, status, created_at
- `list_filter`: status, created_at
- `search_fields`: sender_name, sender_email, subject, message
- `readonly_fields`: created_at, updated_at
- Fieldsets: Sender / Message / Status / Timestamps

---

## Migration Created

```
gallery/migrations/0011_visitor_message.py
```

Command used:
```
python manage.py makemigrations gallery --name visitor_message
```

---

## Commands Run

```
python manage.py makemigrations gallery --name visitor_message
python manage.py check
python manage.py test gallery --verbosity=1
```

---

## Validation / Test Results

```
System check identified no issues (0 silenced).
Ran 110 tests in 46.895s
OK
```

All pre-existing tests pass. No new tests were added (the existing test suite does not have a per-feature test pattern for new public endpoints that would warrant adding tests at this stage; tests can be added in a follow-up).

---

## Intentionally Not Implemented

- Email sending / email notifications
- Frontend integration
- Chat system
- Visitor user accounts / login
- Rate limiting (no existing pattern in the project)
- CAPTCHA
- Admin reply functionality
- Pagination or listing endpoint for visitors
- Any unrelated refactoring

---

## Security Notes

- Field max lengths enforce reasonable abuse limits (name 120, email 254, subject 180).
- Message is `TextField` with no artificial size limit (consistent with existing model patterns).
- Endpoint is write-only: visitors cannot list or read messages.
- `status` field cannot be set by visitors — it is excluded from the write serializer input.
- No sensitive internal fields are exposed in the public response.
