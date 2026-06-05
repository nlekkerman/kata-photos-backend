# Backend Observability Phase 10A Report

## Summary

Added structured `logger.error()` calls to `gallery/services/cloudflare_images.py`,
which previously had no logging at all. Added a missing view-layer `logger.error()`
call in `gallery/views.py` for the Cloudflare Images upload path. No other files
were changed. No models, migrations, serializers, URL patterns, or frontend files
were modified.

---

## Files Changed

| File | Change |
|---|---|
| `gallery/services/cloudflare_images.py` | Added `import logging`, `logger = logging.getLogger(__name__)`; added `logger.error()` calls for HTTP errors, network errors, and API non-success |
| `gallery/views.py` | Added `logger.error()` before `raise CloudflareServiceError` in `_save_media_item_with_cloudflare` |

---

## Existing Logging Audit

### `gallery/views.py` — before this phase

| Location | Event logged |
|---|---|
| `VideoClipDirectUploadView` | `CloudflareStreamUploadError` on direct upload |
| `VideoClipSyncView` | `CloudflareStreamError` on sync |
| `AdminVideoDirectUploadView` | `CloudflareStreamUploadError` on direct upload |
| `AdminVideoRefreshStatusView` | `CloudflareStreamError` on refresh-status |
| `VisitorMessageReplyView` | Email send failure |
| `_save_media_item_with_cloudflare` | **Missing** — `CloudflareUploadError` raised without logging |

### `gallery/services/cloudflare_stream.py` — before this phase

| Location | Event logged |
|---|---|
| `_safe_get` | HTTP error (status, URL, response body truncated to 1000 chars) |
| `_safe_get` | Network/OS error |
| `create_direct_upload` | HTTP error |
| `create_direct_upload` | Network/OS error |
| `create_direct_upload` | API non-success (error codes) |
| `get_video_details` | HTTP error |
| `get_video_details` | Network/OS error |

All token values are excluded from log messages — only `status_code`, `url`, and
the response body (truncated) are logged. This was already correct in
`cloudflare_stream.py`.

### `gallery/services/cloudflare_images.py` — before this phase

No logging at all. HTTP errors, network errors, and API non-success responses
were silently converted to `CloudflareUploadError` exceptions without any log
entry.

---

## Changes Made

### `gallery/services/cloudflare_images.py`

Added `logging` import and module-level logger:

```python
import logging
logger = logging.getLogger(__name__)
```

Added `logger.error()` for three failure modes:

```python
# HTTP error
logger.error(
    "Cloudflare Images API HTTP error: status=%s url=%s response_body=%r",
    exc.code,
    api_url,
    error_body[:1000],
)

# Network/OS error
logger.error("Cloudflare Images network error: url=%s exc=%r", api_url, exc)

# API non-success (success=false in JSON body)
logger.error(
    "Cloudflare Images API non-success: url=%s errors=%r",
    api_url,
    errors,
)
```

**Security:** The `api_token` is never included in any log message. Only the
URL, HTTP status, and the (already-public) error response body are logged.
The `error_body` is truncated to 1000 characters to prevent log flooding.

---

### `gallery/views.py` — `_save_media_item_with_cloudflare`

Added view-layer logging before re-raising as HTTP 502:

```python
except CloudflareUploadError as exc:
    logger.error(
        "Cloudflare Images upload error for album pk=%s filename=%r: %s",
        album.pk,
        uploaded_file.name,
        exc,
    )
    raise CloudflareServiceError(detail=str(exc))
```

This provides request-level context (album PK, filename) that the service-layer
log alone cannot supply.

---

## Logging Coverage After This Phase

| Failure Event | Logged at service layer | Logged at view layer |
|---|---|---|
| CF Stream direct upload failure | Yes (stream service) | Yes (view) |
| CF Stream sync/refresh failure | Yes (stream service) | Yes (view) |
| CF Images HTTP error | **Now yes** (images service) | **Now yes** (view) |
| CF Images network error | **Now yes** (images service) | **Now yes** (view) |
| CF Images API non-success | **Now yes** (images service) | **Now yes** (view) |
| CF Images not configured | No (raises ValueError) | n/a |
| Email send failure | n/a | Yes (view) |
| complete-upload: invalid state | No (silent pass-through) | n/a |

---

## Logging Not Added (By Design)

| Event | Reason excluded |
|---|---|
| Successful uploads | Not errors; INFO-level logging not added to avoid noise |
| `complete-upload` state transitions | Informational; not a failure |
| Admin PATCH/DELETE actions | Not failure conditions |
| Request-level access logging | Handled by Django's `django.request` logger |
| CF Stream `status=failed` forced-public-off | Already a known-safe safety rule, not an error |

---

## Log Configuration

No changes to `config/settings.py` or `LOGGING` were made. Django's default
logging configuration forwards `ERROR`-level log records from any logger named
`gallery.*` to the root logger, which in production (Heroku) writes to stdout
and is captured by the Heroku log drain.

To enable structured logging in production, add to `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'gallery': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
```

This is optional — Heroku captures stdout/stderr automatically. Adding explicit
`LOGGING` config is recommended when a log aggregation service (e.g., Papertrail,
Logentries, Sentry) is added.

---

## Sentry / External Monitoring

The project does not currently use Sentry or any paid monitoring SDK.
`django-sentry-sdk` could be added in a future phase with a single
`settings.py` integration:

```python
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""), ...)
```

This is not implemented here. The standard Python `logging` approach adopted in
this phase is a safe, zero-dependency first step that will automatically forward
error records to Sentry if the SDK is added later.

---

## Validation

```
python manage.py check
# System check identified no issues (0 silenced).

python manage.py test gallery --verbosity=1
# Ran 258 tests in ~105s
# OK
```

No new tests were added in this phase. The logging paths are exercised by
existing Cloudflare upload mock tests which verify the HTTP 502 response,
confirming the code path is reachable. Dedicated logging assertion tests
were not added to keep the diff minimal.

---

## What Was Not Changed

- `gallery/models.py` — not touched
- `gallery/migrations/` — no migrations created
- `gallery/serializers.py` — not touched
- `gallery/urls.py` — not touched
- `gallery/public_urls.py` — not touched
- `config/settings.py` — not touched
- Admin endpoints — not changed
- Frontend files — not modified
