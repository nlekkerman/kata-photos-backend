# Backend CORS Local Frontend Setup Report

**Date:** 2026-05-29  
**Phase:** Backend — CORS support for local Vite frontend

---

## Package installed

- `django-cors-headers==4.9.0` (was already present in venv; added to `requirements.txt`)

---

## Files changed

| File | Change |
|---|---|
| `requirements.txt` | Added `django-cors-headers==4.9.0` |
| `config/settings.py` | Added `corsheaders` to `INSTALLED_APPS`, `CorsMiddleware` to `MIDDLEWARE`, `CORS_ALLOWED_ORIGINS` setting |
| `.env.example` | Added `CORS_ALLOWED_ORIGINS` entry |
| `.env` | Added `CORS_ALLOWED_ORIGINS` entry (local, not committed) |

---

## `INSTALLED_APPS` update

`corsheaders` added beside `rest_framework`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    "gallery",
]
```

---

## Middleware position

`CorsMiddleware` placed as the second entry, immediately after `SecurityMiddleware` and before `CommonMiddleware`, as required by `django-cors-headers`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    ...
]
```

---

## `CORS_ALLOWED_ORIGINS` values

Env-driven with safe local defaults:

```python
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
```

Allowed origins (local default):
- `http://localhost:5173`
- `http://127.0.0.1:5173`

`CORS_ALLOW_ALL_ORIGINS = True` was **not** used.

---

## `.env.example` update

```env
ALLOWED_HOSTS=127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Validation

Command run:

```bash
python manage.py check
```

Result:

```
System check identified no issues (0 silenced).
```

---

## Frontend browser verification

Not performed — frontend not available during this phase. To verify manually:

1. Start backend: `python manage.py runserver`
2. Open frontend at `http://localhost:5173/gallery`
3. Confirm no CORS errors in browser console
4. Optionally check `http://127.0.0.1:8000/api/gallery/albums/?lang=en` directly

---

## Unchanged components

- Gallery models — **not changed**
- Gallery serializers — **not changed**
- Gallery views — **not changed**
- API response contracts — **not changed**
- Media upload logic — **not changed**
- Authentication — **not added**
- CSRF trusted origins — **not changed** (GET-only public API; deferred to a future phase)

---

## Assumptions

- `django-cors-headers` 4.9.0 was already installed in the venv; `pip freeze` made it explicit in `requirements.txt`.
- Local `.env` updated in place; it is gitignored and not committed.
- No production origins hardcoded; override via `CORS_ALLOWED_ORIGINS` env var when deploying.
