# Cloudflare Stream — SyntaxError Bugfix Report

**Date:** 2026-06-01  
**Endpoint affected:** `POST /api/gallery/videos/direct-upload/`  
**File changed:** `gallery/services/cloudflare_stream.py`

---

## Problem

Django crashed with:

```
SyntaxError: cannot assign to function call here. Maybe you meant '==' instead of '='?
  File "gallery/services/cloudflare_stream.py", line 166
```

The error was a silent syntax bomb — Python never imported that code path until the endpoint was hit, so it bypassed `manage.py check` and the test suite (which mocked the service).

---

## Root Cause

Two separate lines inside `create_direct_upload()` were accidentally merged into one invalid statement:

**Before (invalid — line 166):**
```python
_check_configured(account_id, api_token) = datetime.now(tz=timezone.utc) + timedelta(seconds=expiry_seconds)
```

The left-hand side is a function call, which is not a valid assignment target in Python.

---

## Fix

Split the merged line back into the two original statements:

**After (valid):**
```python
_check_configured(account_id, api_token)
expiry_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=expiry_seconds)
```

---

## Files Changed

| File | Change |
|------|--------|
| `gallery/services/cloudflare_stream.py` | Line 166: split one invalid merged line into two valid lines |

---

## Validation

```
python -m py_compile gallery/services/cloudflare_stream.py  → OK
python manage.py check                                       → 0 issues
python manage.py test --verbosity=2                         → 44/44 passed
```

---

## Prevention Note

`py_compile` catches this class of syntax error immediately, before any test or server start:

```bash
python -m py_compile gallery/services/cloudflare_stream.py
```

Add this to the pre-commit or CI pipeline for all service modules. It costs milliseconds and catches syntax bombs that `manage.py check` misses because Django only imports a module when its code path is first exercised.
