# Visitor Message Email Reply Endpoint

**Date:** 2026-06-05

---

## Summary

Added an admin-only email reply endpoint for `VisitorMessage` records.
When an admin POSTs a reply, Django's built-in email system sends a plain-text
email to the original sender.  On success the message status is set to
`replied` and `replied_at` is stamped.  On any email failure the message is
left untouched and an HTTP 502 is returned.

No public API changes.  No frontend changes.  No HTML templates.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/models.py` | Added `replied_at` to `VisitorMessage`; added `VisitorMessageReply` model |
| `gallery/migrations/0014_visitor_message_replied_at_reply_model.py` | Migration for the above |
| `config/settings.py` | Added email backend settings (all from environment variables) |
| `gallery/serializers.py` | Added `VisitorMessageReplyRequestSerializer`; added `VisitorMessageReply` import |
| `gallery/views.py` | Added `VisitorMessageReplyView`; added `VisitorMessageReply` import |
| `gallery/urls.py` | Added URL for reply endpoint; added `VisitorMessageReplyView` import |
| `gallery/admin.py` | Added `VisitorMessageReplyAdmin`; updated `VisitorMessageAdmin` with `replied_at` in `readonly_fields` and fieldsets |
| `gallery/tests.py` | Added `VisitorMessageReplyViewTests` (16 tests) |

**Total: 8 files changed.**

---

## Endpoint Added

```
POST /api/gallery/admin/visitor-messages/<pk>/reply/
```

### Payload

```json
{
  "reply_subject": "Re: Question about the video",
  "reply_body": "Hello, thank you for your message..."
}
```

### Success Response — HTTP 200

```json
{
  "detail": "Reply sent.",
  "replied_at": "2026-06-05T14:23:00.000000Z"
}
```

### Error Responses

| Condition | Status |
|---|---|
| Anonymous or non-staff request | 401 / 403 |
| Message not found | 404 |
| Missing or blank `reply_subject` | 400 |
| Missing or blank `reply_body` | 400 |
| `sender_email` absent on message | 400 |
| Email backend failure | 502 |

---

## Model / Migration Changes

### `VisitorMessage` — new field

```python
replied_at = models.DateTimeField(null=True, blank=True)
```

Set by the reply endpoint only.  `null` means the message has never been
replied to via the endpoint, even if `status` was manually set to `replied`
via the admin bulk action.

### `VisitorMessageReply` — new model

| Field | Type | Notes |
|---|---|---|
| `visitor_message` | FK → `VisitorMessage` | `CASCADE`; `related_name='replies'` |
| `reply_subject` | `CharField(max_length=250)` | |
| `reply_body` | `TextField` | |
| `sent_at` | `DateTimeField(auto_now_add=True)` | |
| `sent_by` | FK → `auth.User`, `null=True` | `SET_NULL`; preserves record if user deleted |

One record is created per successful reply send.  Multiple replies per message
are supported.

### Migration

`gallery/migrations/0014_visitor_message_replied_at_reply_model.py`

---

## Permission Used

`IsAdminUser` (Django REST Framework built-in).
Requires `is_staff=True`.  Session or token auth both work.
Visitors receive HTTP 403.

---

## Email Sending Behaviour

1. Load `VisitorMessage` by `pk` — 404 if not found.
2. Reject with 400 if `sender_email` is empty.
3. Validate `reply_subject` and `reply_body` — 400 on blank or missing.
4. Build plain-text body: admin reply, then a quoted block with original
   sender name, subject, video title (if any), timestamp (if any), and
   original message text.
5. Call `django.core.mail.send_mail(fail_silently=False)`.
6. **On success:** set `status = 'replied'`, `replied_at = timezone.now()`,
   save with `update_fields`, create `VisitorMessageReply` record.
7. **On any exception from `send_mail`:** log the error, return HTTP 502.
   Message status and `replied_at` are **not** modified.  No reply record
   is created.

---

## Failure Behaviour

Email failures are caught as a broad `except Exception` around `send_mail`.
This covers `SMTPException`, connection errors, misconfiguration, and any
other transport failure.  The error is logged at `ERROR` level via the
`gallery` logger.  The view returns:

```json
{"detail": "Failed to send email. The message was not updated."}
```

with HTTP 502.

---

## Email Settings Discovered

No email settings existed in `config/settings.py` before this change.
The following settings were added, all sourced from environment variables:

| Setting | Env Var | Default |
|---|---|---|
| `EMAIL_BACKEND` | `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` |
| `EMAIL_HOST` | `EMAIL_HOST` | `""` |
| `EMAIL_PORT` | `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `EMAIL_USE_TLS` | `True` |
| `EMAIL_USE_SSL` | `EMAIL_USE_SSL` | `False` |
| `EMAIL_HOST_USER` | `EMAIL_HOST_USER` | `""` |
| `EMAIL_HOST_PASSWORD` | `EMAIL_HOST_PASSWORD` | `""` |
| `DEFAULT_FROM_EMAIL` | `DEFAULT_FROM_EMAIL` | `webmaster@localhost` |

**Local / dev:** the console backend (default) prints email to stdout.
No SMTP server required.

**Production (e.g. Heroku):** set all of the above as config vars.
No provider SDK is needed — Django's built-in SMTP backend works with
any provider (SendGrid, Mailgun, Postmark, Amazon SES, etc.) via their
SMTP relay credentials.  Credentials are never committed to source.

---

## Commands Run

```
python manage.py makemigrations gallery --name visitor_message_replied_at_reply_model
python manage.py check
python manage.py test gallery --verbosity=1
```

## Test Results

```
System check identified no issues (0 silenced).
Ran 126 tests in 61.787s
OK
```

16 new tests added in `VisitorMessageReplyViewTests`.  110 pre-existing tests
unchanged and still passing.

---

## What Was Intentionally Not Implemented

- HTML email templates
- Email queuing or async sending
- Rate limiting on the reply endpoint
- `GET` endpoint to list or retrieve replies
- Auto-reply on message creation
- Reply to `VideoTimestampComment` (public comment system — separate)
- Any public API changes
- Any frontend changes
- Likes, reactions, or chat
- Custom moderation dashboard
