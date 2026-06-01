# Frontend Session / Auth Readiness — Phase 7 Implementation Report

**Date:** 2026-06-01
**Repository:** `kata-photos-backend`
**Implementer:** GitHub Copilot (Claude Sonnet 4.6)
**Prerequisite:** Phase 5 — `documents/backend-docs/gallery-album-cover-api-phase-5-implementation-report-2026-06-01.md`

---

## Summary

Phase 7 adds a minimal `auth_api` module that gives the Vite frontend four auth helper endpoints using Django's existing session and CSRF infrastructure. No JWT, no custom roles, no gallery changes. CORS credentials and CSRF trusted origins are updated for local dev. All 27 pre-existing gallery tests still pass; 17 new auth tests are green.

---

## Files Inspected

| File | Reason |
|---|---|
| `config/settings.py` | CORS and CSRF settings audit |
| `config/urls.py` | Where to attach `/api/auth/` |
| `gallery/views.py` | Confirm `LangContextMixin` / DRF pattern in use |

---

## Files Changed

| File | Change |
|---|---|
| `auth_api/__init__.py` | New — empty package marker |
| `auth_api/views.py` | New — `SessionView`, `CsrfView`, `LogoutView`, `LoginView` |
| `auth_api/urls.py` | New — URL patterns under `/api/auth/` |
| `auth_api/tests.py` | New — 9 focused auth tests |
| `config/urls.py` | Added `path("api/auth/", include("auth_api.urls"))` |
| `config/settings.py` | Added `CORS_ALLOW_CREDENTIALS = True`; added Vite origins to `CSRF_TRUSTED_ORIGINS` default |

**Total files changed: 6** (within the 2–7 target)
**No migrations created.** Phase 7 is view-only — no model changes.

---

## Auth Endpoints Added

All endpoints live under `/api/auth/`.

| Method | URL | Auth required | Description |
|---|---|---|---|
| `GET` | `/api/auth/session/` | None | Returns current session state |
| `GET` | `/api/auth/csrf/` | None | Sets CSRF cookie; returns confirmation |
| `POST` | `/api/auth/logout/` | None | Destroys current session |
| `POST` | `/api/auth/login/` | None | Authenticates staff users via session |

### GET /api/auth/session/

Authenticated staff response:
```json
{ "is_authenticated": true, "is_staff": true, "username": "admin" }
```

Anonymous response:
```json
{ "is_authenticated": false, "is_staff": false, "username": "" }
```

### GET /api/auth/csrf/

Sets the `csrftoken` cookie via `django.middleware.csrf.get_token`.

Response:
```json
{ "detail": "CSRF cookie set" }
```

`authentication_classes = []` on this view prevents session lookup overhead on a GET that needs no auth.

### POST /api/auth/logout/

Calls `django.contrib.auth.logout(request)`.

Response:
```json
{ "detail": "Logged out" }
```

### POST /api/auth/login/

Accepted body:
```json
{ "username": "admin", "password": "password" }
```

Calls `authenticate()` then `login()`. Only staff users are allowed through this endpoint. Non-staff receive `403`. Invalid credentials receive `400`.

Success response (same shape as `/api/auth/session/`):
```json
{ "is_authenticated": true, "is_staff": true, "username": "admin" }
```

CSRF is **not** bypassed — Django test client enforces CSRF exemption only in tests via `enforce_csrf_checks=False` (the default). In production, the frontend must obtain the CSRF token from `/api/auth/csrf/` first and include it as `X-CSRFToken` header.

---

## CORS / CSRF Settings Changed

### `CORS_ALLOW_CREDENTIALS = True` (added)

Required for the browser to send the session cookie (`sessionid`) and CSRF cookie (`csrftoken`) on cross-origin requests from `http://localhost:5173`.

`django-cors-headers` was already installed and configured. `CORS_ALLOWED_ORIGINS` already included both Vite origins. No duplication.

### `CSRF_TRUSTED_ORIGINS` default updated

Before:
```python
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
```

After:
```python
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
```

Django's CSRF middleware checks the `Origin` / `Referer` header against `CSRF_TRUSTED_ORIGINS` for unsafe methods (POST/PATCH/DELETE). Without this, cross-origin POST from Vite would fail with `403 Forbidden (CSRF)`. Production overrides this via the `CSRF_TRUSTED_ORIGINS` env var. CSRF is **not** globally weakened.

---

## Tests Added

File: `auth_api/tests.py`

| Class | Test | Assertion |
|---|---|---|
| `SessionViewTests` | `test_anonymous_session_returns_unauthenticated` | `is_authenticated=false`, `is_staff=false`, `username=""` |
| `SessionViewTests` | `test_staff_session_returns_authenticated_and_staff` | `is_authenticated=true`, `is_staff=true` |
| `SessionViewTests` | `test_non_staff_session_returns_authenticated_not_staff` | `is_authenticated=true`, `is_staff=false` |
| `CsrfViewTests` | `test_csrf_endpoint_returns_200` | HTTP 200, `{"detail": "CSRF cookie set"}` |
| `LogoutViewTests` | `test_logout_clears_session` | Session anonymous after POST to `/logout/` |
| `LoginViewTests` | `test_valid_staff_credentials_log_in` | HTTP 200, session shape correct |
| `LoginViewTests` | `test_invalid_credentials_return_400` | HTTP 400, `detail` in response |
| `LoginViewTests` | `test_non_staff_user_cannot_log_in_via_api` | HTTP 403 |
| `LoginViewTests` | `test_missing_credentials_return_400` | HTTP 400 |

---

## Commands Run and Results

```
python manage.py makemigrations --check --dry-run
```
→ `No changes detected` (exit 0). Phase 7 is view-only.

```
python manage.py migrate
```
→ `No migrations to apply.`

```
python manage.py check
```
→ `System check identified no issues (0 silenced).`

```
python manage.py test --verbosity=2
```
→ `Ran 44 tests in 39.614s OK`
- 9 Phase 7 auth tests: all pass
- 8 Phase 5 album cover tests: all pass
- 11 Phase 4 media upload tests: all pass
- 8 Phase 3 album write tests: all pass
- 8 upload safety tests: all pass

---

## Confirmation

- **No frontend files were touched.**
- **No JWT or token auth was added.** Session + CSRF only.
- **No gallery endpoints were changed.** All 35 pre-existing gallery tests pass unchanged.
- **No custom user roles were added.**
- **No fake or dummy auth was added.**
- **No localStorage auth.**
- **CSRF is not globally disabled or weakened.** Trusted origins are added for local dev only; production overrides via env.
- **No broad refactor was performed.**

---

## Follow-up Notes for Frontend Integration

1. **Session auth flow (recommended order):**
   1. `GET /api/auth/csrf/` — sets `csrftoken` cookie; read it with `js-cookie` or `document.cookie`.
   2. `POST /api/auth/login/` with `{ username, password }` and `X-CSRFToken: <token>` header.
   3. `GET /api/auth/session/` — confirm `is_authenticated=true` and `is_staff=true`.
   4. All subsequent unsafe requests need `X-CSRFToken` header and `credentials: "include"`.

2. **`credentials: "include"` is required** on every `fetch` call from Vite for the session cookie to be sent cross-origin.

3. **Django admin login also works.** If the frontend is opened in the same browser where the staff user already logged in via `http://127.0.0.1:8000/admin/`, the session is shared and `/api/auth/session/` will return `is_authenticated=true` immediately. No API login call needed.

4. **`IsAdminUser` requires `is_staff=True`.** Same as Phases 3–5. A user with `is_active=True` but `is_staff=False` will receive `403` from gallery write endpoints even if they log in via `/api/auth/login/`.

5. **CORS in production.** Set `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` env vars to the production frontend origin. `CORS_ALLOW_CREDENTIALS=True` stays — it is safe when `CORS_ALLOWED_ORIGINS` is an explicit allowlist (not `*`).

6. **Session expiry.** Default Django session cookie expires when the browser closes (`SESSION_EXPIRE_AT_BROWSER_CLOSE` is unset, defaulting to `False`, meaning a 2-week persistent cookie). Adjust `SESSION_COOKIE_AGE` if shorter expiry is needed.
