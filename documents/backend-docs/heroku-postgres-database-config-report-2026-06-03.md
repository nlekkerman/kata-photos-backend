# Heroku Postgres Database Config Report
**Date:** 2026-06-03  
**Task:** Phase 1 — Django database config + Heroku Postgres support

---

## Files changed

| File | Change |
|------|--------|
| `config/settings.py` | Replaced hardcoded SQLite `DATABASES` block with `dj_database_url.config()` fallback; added `import dj_database_url` |
| `requirements.txt` | Appended `dj-database-url` and `psycopg2-binary` |
| `.env.example` | Added `DATABASE_URL=` entry with explanatory comment |

**Approximate changed-line count:** ~18 lines changed/added across 3 files.

---

## Dependencies added

| Package | Purpose |
|---------|---------|
| `dj-database-url` | Parses `DATABASE_URL` env var into Django `DATABASES` dict |
| `psycopg2-binary` | PostgreSQL adapter required when `DATABASE_URL` points to Postgres |

Both were appended to `requirements.txt` without version pins (matches the style of `Pillow==11.2.1` being the last pinned entry; these two are infrastructure dependencies where Heroku controls the environment).

`dj-database-url` was already present in the local venv (version 3.1.2). No venv reinstall needed.

---

## Exact database behavior

### Local without `DATABASE_URL`

```python
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}
```

- `dj_database_url.config()` reads `DATABASE_URL` from the environment.
- When `DATABASE_URL` is absent, it uses the `default=` parameter: `sqlite:///…/db.sqlite3`.
- `ssl_require=not DEBUG` → `ssl_require=False` locally (since `DEBUG=True` in `.env`).
- Engine: `django.db.backends.sqlite3` — confirmed by shell sanity check.

### Heroku with `DATABASE_URL`

- Heroku Postgres add-on sets `DATABASE_URL=postgres://…` automatically in config vars.
- `dj_database_url.config()` parses it into the correct `ENGINE`, `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`.
- `conn_max_age=600` enables persistent connections (60-second pool lifetime) — appropriate for Heroku dynos.
- `ssl_require=not DEBUG` → `ssl_require=True` in production (since `DEBUG=False` on Heroku).
- Engine: `django.db.backends.postgresql`.

### SQLite local fallback

Confirmed working — the `default=` SQLite URL is used when `DATABASE_URL` is unset.

---

## Secrets

No real credentials were added or printed. `DATABASE_URL=` in `.env.example` has an empty value.

---

## Commands run and results

| Command | Result |
|---------|--------|
| `python manage.py check` | System check identified no issues (0 silenced) |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py shell -c "...print(settings.DATABASES['default']['ENGINE'])"` | `django.db.backends.sqlite3` ✓ |
| `python manage.py test --verbosity=1` | 51 tests, 0 failures, 0 errors — OK |

---

## What was not touched

- No model changes
- No migrations created
- No views, serializers, or URLs modified
- No `Procfile`, `runtime.txt`, `gunicorn`, `whitenoise`
- No cookie/security settings
- No CORS/CSRF production settings
- No Cloudflare settings
- No frontend files
- `.env` not edited

---

## Remaining deployment blockers still pending

| Blocker | Status |
|---------|--------|
| `Procfile` (web + release commands) | Pending |
| `runtime.txt` (Python version pin) | Pending |
| `gunicorn` in `requirements.txt` | Pending |
| `whitenoise` for static file serving | Pending |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Pending |
| `SECURE_PROXY_SSL_HEADER` for Heroku TLS | Pending |
| `SESSION_COOKIE_SAMESITE='None'`, `CSRF_COOKIE_SAMESITE='None'` | Pending |
| `CSRF_TRUSTED_ORIGINS` with Netlify URL | Pending (env var exists, value needed) |
| `CORS_ALLOWED_ORIGINS` with Netlify URL | Pending (env var exists, value needed) |
| Heroku config vars populated | Pending |
