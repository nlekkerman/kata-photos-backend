# Backend Cross-Site Session Cookie Fix — 2026-06-04

## Summary

Django's default cookie policy (`SameSite=Lax`, `Secure=False`) blocks cross-site session
cookies when the frontend (`https://kataphotos.com`) calls the Heroku backend
(`https://kata-wild-backend-5b989da54ce2.herokuapp.com`) using `fetch(..., credentials: "include")`.

The browser silently drops cookies set with `SameSite=Lax` on cross-site responses, so the
session established by `POST /api/auth/login/` is never sent back on the subsequent
`GET /api/auth/session/`, which returns `is_authenticated: false`.

The fix adds four env-var-driven settings to `config/settings.py` so that, when Heroku config
vars are set, cookies are emitted as `SameSite=None; Secure`, which the browser will attach to
all credentialed cross-origin requests.

---

## Evidence

### Bad cookie headers (before fix, production defaults)

```
set-cookie: csrftoken=...; Path=/; SameSite=Lax
set-cookie: sessionid=...; HttpOnly; Path=/; SameSite=Lax
```

- `SameSite=Lax` — browser will **not** send these cookies on cross-site sub-resource requests
  (i.e., `fetch` from `https://kataphotos.com` to `https://kata-wild-backend-5b989da54ce2.herokuapp.com`).
- Missing `Secure` — required by browsers whenever `SameSite=None` is used.

### Why this breaks session auth

1. `POST /api/auth/login/` — succeeds (200), Django creates a session and sets `sessionid` cookie.
2. Browser receives the cookie but, because `SameSite=Lax` is set and this is a cross-site fetch,
   it does **not** store the cookie for cross-origin use.
3. `GET /api/auth/session/` — the browser sends the request without the `sessionid` cookie.
4. Django finds no session → returns `{ "is_authenticated": false }`.

`CORS_ALLOW_CREDENTIALS = True` and correct CORS headers are already in place; the cookie
attributes were the only missing piece.

---

## Files Inspected

- `config/settings.py` — all settings, including CORS, CSRF, session, and env-var helpers.

---

## Files Changed

- `config/settings.py`

---

## Settings Before

| Setting | Value (effective default) |
|---|---|
| `SESSION_COOKIE_SAMESITE` | `"Lax"` (Django default, not set) |
| `CSRF_COOKIE_SAMESITE` | `"Lax"` (Django default, not set) |
| `SESSION_COOKIE_SECURE` | `False` (Django default, not set) |
| `CSRF_COOKIE_SECURE` | `False` (Django default, not set) |
| `CORS_ALLOW_CREDENTIALS` | `True` |
| `CORS_ALLOWED_ORIGINS` | env-var driven, defaults include `https://kata-photos.netlify.app` |
| `CSRF_TRUSTED_ORIGINS` | env-var driven, defaults include `https://kata-photos.netlify.app` |

---

## Settings After

The following block was added to `config/settings.py` immediately after `CORS_ALLOW_CREDENTIALS`:

```python
# Cross-site session cookies — required for production where the frontend
# (https://kataphotos.com) and backend (Heroku) are on different sites.
# SameSite=None; Secure is required for credentialed cross-origin fetch().
# Defaults keep local dev working over plain HTTP with SameSite=Lax.
# On Heroku set: SESSION_COOKIE_SAMESITE=None, CSRF_COOKIE_SAMESITE=None,
#                SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False").lower() == "true"
```

| Setting | Local dev (default) | Production (Heroku env vars set) |
|---|---|---|
| `SESSION_COOKIE_SAMESITE` | `"Lax"` | `"None"` |
| `CSRF_COOKIE_SAMESITE` | `"Lax"` | `"None"` |
| `SESSION_COOKIE_SECURE` | `False` | `True` |
| `CSRF_COOKIE_SECURE` | `False` | `True` |
| `CORS_ALLOW_CREDENTIALS` | `True` | `True` (unchanged) |

---

## Heroku Config Vars Required

Set these in the Heroku dashboard (Settings → Config Vars) or via CLI:

```
SESSION_COOKIE_SAMESITE=None
CSRF_COOKIE_SAMESITE=None
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Additionally, confirm these existing vars include the custom domain:

```
CORS_ALLOWED_ORIGINS=https://kataphotos.com,https://kata-photos.netlify.app
CSRF_TRUSTED_ORIGINS=https://kataphotos.com,https://kata-photos.netlify.app,https://kata-wild-backend-5b989da54ce2.herokuapp.com
```

> The default fallback values in `settings.py` reference `https://kata-photos.netlify.app`
> but not `https://kataphotos.com`. If the frontend is served exclusively from the custom
> domain, both env vars must be set on Heroku to include `https://kataphotos.com`.

---

## Validation

### Django system check

```
System check identified no issues (0 silenced).
```

Command run: `.venv\Scripts\python.exe manage.py check`

---

## Manual Production Verification Steps

1. Open `https://kataphotos.com/admin/login` (or whichever page triggers login).
2. Open browser DevTools → Network tab.
3. Submit login credentials to trigger `POST /api/auth/login/`.
4. In the Response Headers for that request, confirm:
   ```
   set-cookie: sessionid=...; HttpOnly; Path=/; SameSite=None; Secure
   set-cookie: csrftoken=...; Path=/; SameSite=None; Secure
   ```
5. Confirm the cookies appear in DevTools → Application → Cookies for
   `kata-wild-backend-5b989da54ce2.herokuapp.com`.
6. Inspect the immediately following `GET /api/auth/session/` request.
7. Confirm the `Cookie` request header contains `sessionid=...`.
8. Confirm the response body returns:
   ```json
   { "is_authenticated": true, "username": "..." }
   ```
   instead of `{ "is_authenticated": false }`.
