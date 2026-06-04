# Backend CSRF JSON Token Fix — 2026-06-04

## Summary

`GET /api/auth/csrf/` already called `get_token(request)` to force Django to set the CSRF
cookie, but discarded the return value and responded with `{"detail": "CSRF cookie set"}`.

In the cross-domain production setup (`https://kataphotos.com` → Heroku backend) the frontend
cannot read the `csrftoken` cookie via `document.cookie` because the cookie belongs to the
backend's domain. This meant the frontend had no way to obtain the token value, so it sent an
empty `X-CSRFToken` header on unsafe requests, causing Django to reject them with:

```
{"detail": "CSRF Failed: CSRF token from the 'X-Csrftoken' HTTP header has incorrect length."}
```

The fix is one line: return the value that `get_token(request)` already produces.

---

## Files Changed

| File | Change |
|---|---|
| `auth_api/views.py` | `CsrfView.get` now returns `{"csrfToken": get_token(request)}` |
| `auth_api/tests.py` | `CsrfViewTests` updated to assert `csrfToken` key is present and non-empty |

---

## What Changed

### `auth_api/views.py` — before

```python
def get(self, request):
    get_token(request)  # sets the cookie on the response
    return Response({"detail": "CSRF cookie set"})
```

### `auth_api/views.py` — after

```python
def get(self, request):
    return Response({"csrfToken": get_token(request)})
```

`get_token(request)` both generates/retrieves the token *and* marks it so Django attaches the
`Set-Cookie: csrftoken=...` header on the response — identical behaviour to the previous call,
but now the value is also returned to the caller.

### `auth_api/tests.py` — before

```python
class CsrfViewTests(TestCase):
    def test_csrf_endpoint_returns_200(self):
        response = self.client.get(reverse("auth-csrf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"detail": "CSRF cookie set"})
```

### `auth_api/tests.py` — after

```python
class CsrfViewTests(TestCase):
    def test_csrf_endpoint_returns_200_with_token(self):
        response = self.client.get(reverse("auth-csrf"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("csrfToken", data)
        self.assertTrue(len(data["csrfToken"]) > 0)
```

---

## Why This Was Needed

Browsers enforce the **same-origin policy** on cookies. When the frontend is served from
`https://kataphotos.com` and the backend from `https://kata-wild-backend-5b989da54ce2.herokuapp.com`,
the `csrftoken` cookie set by the backend is **not accessible** via `document.cookie` from the
frontend page. The only reliable way for the frontend to obtain the token is to read it from the
JSON response body.

---

## Validation

### Tests

```
Ran 9 tests in 10.094s
OK
```

All auth_api tests pass, including the updated `test_csrf_endpoint_returns_200_with_token`.

### Commands Run

```
.venv\Scripts\python.exe manage.py check
# → System check identified no issues (0 silenced)

.venv\Scripts\python.exe manage.py test auth_api --verbosity=2
# → Ran 9 tests ... OK
```

---

## Deployment Notes

No new environment variables or Heroku config vars are required for this change.

Confirm these config vars remain set on Heroku (from prior cross-site cookie fix):

```
SESSION_COOKIE_SAMESITE=None
CSRF_COOKIE_SAMESITE=None
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CORS_ALLOWED_ORIGINS=https://kataphotos.com,...
CSRF_TRUSTED_ORIGINS=https://kataphotos.com,...
```

---

## Frontend Follow-Up Needed

**Frontend must update `getCsrfToken()` (or equivalent) to read `csrfToken` from the JSON
response body instead of `document.cookie`.**

Example pattern:

```js
async function getCsrfToken() {
  const res = await fetch("https://kata-wild-backend-5b989da54ce2.herokuapp.com/api/auth/csrf/", {
    credentials: "include",
  });
  const data = await res.json();
  return data.csrfToken;   // ← read from body, not document.cookie
}
```

This is the only required frontend change to resolve the empty `X-CSRFToken` header issue.
