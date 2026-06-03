# Heroku Procfile, Runtime, and Gunicorn Report
**Date:** 2026-06-03  
**Task:** Add Heroku process files and WSGI server

---

## Files changed

| File | Change |
|------|--------|
| `Procfile` | Created (new file) |
| `runtime.txt` | Created (new file) |
| `requirements.txt` | Appended `gunicorn` |

**Approximate changed-line count:** 5 lines across 3 files.

---

## Procfile contents

```
web: gunicorn config.wsgi:application
release: python manage.py migrate
```

- `config.wsgi:application` confirmed from `config/wsgi.py` — module is `config`, callable is `application`.
- `release:` phase runs migrations automatically on every Heroku deploy before the web dyno starts.

---

## runtime.txt — Python version chosen

```
python-3.13.1
```

**Reason:** Local venv is Python 3.13.1 (`python --version` confirmed). Python 3.13 is a supported Heroku stack version. Pinning to match local dev avoids cross-version surprises.

---

## Gunicorn dependency status

- Added `gunicorn` (unpinned) to `requirements.txt`.
- Installed into local venv — already present or freshly installed.
- `gunicorn --check-config` cannot run on Windows (gunicorn requires `fcntl`, a Unix-only module). This is expected; gunicorn works on Heroku's Linux dynos. No config error.

---

## Commands run and results

| Command | Result |
|---------|--------|
| `python manage.py check` | 0 issues |
| `python manage.py test --verbosity=1` | 51 tests, 0 failures — OK |
| `gunicorn config.wsgi:application --check-config` | `ModuleNotFoundError: No module named 'fcntl'` — Windows-only limitation, not a config error |

---

## What was not touched

- No model changes
- No migrations
- No views, serializers, or URLs
- No `settings.py`
- No `.env`
- No WhiteNoise / static files
- No CORS/CSRF/cookie settings
- No frontend files

---

## Remaining deployment blockers

| Blocker | Status |
|---------|--------|
| WhiteNoise / static file serving | Pending |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Pending |
| `SECURE_PROXY_SSL_HEADER` for Heroku TLS termination | Pending |
| `SESSION_COOKIE_SAMESITE='None'`, `CSRF_COOKIE_SAMESITE='None'` | Pending |
| `CSRF_TRUSTED_ORIGINS` with production Netlify URL | Pending |
| `CORS_ALLOWED_ORIGINS` with production Netlify URL | Pending |
| Heroku config vars verified and populated | Pending |
