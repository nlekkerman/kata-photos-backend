# Netlify Origin Access Report

**Date:** 2026-06-04  
**Scope:** Allow Netlify frontend to access the production Heroku backend.

---

## Files Changed

| File | Change |
|---|---|
| `config/settings.py` | Updated default fallback values for `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` |
| `.env.example` | Added production example comments for `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` |

---

## Origins / Hosts Added

### `ALLOWED_HOSTS` default
Added: `kata-wild-backend-5b989da54ce2.herokuapp.com`  
Preserved: `127.0.0.1`, `localhost`

### `CORS_ALLOWED_ORIGINS` default
Added: `https://kata-photos.netlify.app`  
Preserved: `http://localhost:5173`, `http://127.0.0.1:5173`

### `CSRF_TRUSTED_ORIGINS` default
Added: `https://kata-photos.netlify.app`, `https://kata-wild-backend-5b989da54ce2.herokuapp.com`  
Preserved: `http://localhost:5173`, `http://127.0.0.1:5173`

---

## CORS Config — Pre-existing?

Yes. `django-cors-headers` was already installed and configured before this change:
- `corsheaders` is in `INSTALLED_APPS`
- `corsheaders.middleware.CorsMiddleware` is in `MIDDLEWARE` (positioned before `CommonMiddleware`)
- `CORS_ALLOWED_ORIGINS` and `CORS_ALLOW_CREDENTIALS = True` were already present
- Only the default fallback value was missing the Netlify origin

---

## CSRF Trusted Origins — Updated?

Yes. `CSRF_TRUSTED_ORIGINS` default fallback was extended to include:
- `https://kata-photos.netlify.app`
- `https://kata-wild-backend-5b989da54ce2.herokuapp.com`

The Heroku backend host is required in `CSRF_TRUSTED_ORIGINS` because Django rejects CSRF-protected requests when the `Origin`/`Referer` header does not match a trusted origin, and the backend itself can be accessed over HTTPS.

---

## Config Pattern

All three settings remain env-var driven. The env vars (`ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`) override the defaults when set on Heroku. The defaults now ensure correct behaviour even when those env vars are not explicitly set in the Heroku config.

---

## Validation Results

```
python manage.py check
System check identified no issues (0 silenced).
```

No errors or warnings. Checked with the project virtualenv.

---

## Files Intentionally Not Touched

- `gallery/models.py`
- `gallery/serializers.py`
- `gallery/views.py`
- `auth_api/views.py`
- All migration files
- All URL files
- All service files
- Frontend (not in this repository)
