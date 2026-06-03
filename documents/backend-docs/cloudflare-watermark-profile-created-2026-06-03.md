# Cloudflare Stream Watermark Profile — Created 2026-06-03

## Status

Watermark profile created and validated successfully.

---

## Profile Details

| Field         | Value                                    |
|---------------|------------------------------------------|
| **UID**       | `29b0fa37be907b876f3c5670cfaf8890`       |
| **Name**      | Kata Dejanovic Photography Watermark     |
| **Opacity**   | 0.55                                     |
| **Padding**   | 0.05                                     |
| **Scale**     | 0.12                                     |
| **Position**  | lowerRight                               |
| **Source PNG**| `C:\Users\nlekk\Downloads\watermark.png` |
| **PNG Size**  | 2,145,309 bytes (original, uncompressed) |
| **PNG Dimensions** | 1536×1024 px (RGBA)                 |

---

## Credentials Used

- **Account ID env var:** `CLOUDFLARE_ACCOUNT_ID` (loaded from `.env`)
- **API Token env var:** `CLOUDFLARE_STREAM_API_TOKEN` (loaded from `.env`)
- No secrets were printed or committed.

---

## API Call

```
POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/stream/watermarks
Authorization: Bearer {CLOUDFLARE_STREAM_API_TOKEN}

Form fields:
  file=@watermark.png  (multipart, image/png)
  name=Kata Dejanovic Photography Watermark
  opacity=0.55
  padding=0.05
  scale=0.12
  position=lowerRight
```

Initial attempts with `position=bottomRight` returned HTTP 400 (invalid field value).
Corrected to `position=lowerRight` per Cloudflare Stream API specification.
The original uncompressed PNG (2.1 MB) was used — compression was tested but not required.

---

## Helper Script

A temporary helper script was created at:

```
scripts/create_cloudflare_watermark_profile.py
```

The script:
- reads credentials from `.env` via `python-dotenv`
- uploads the watermark PNG
- prints only the returned UID
- never prints or commits the API token
- is safe to keep in the repo (no secrets hardcoded)

---

## Environment Variable Updated

`.env` was updated in-place:

```
CLOUDFLARE_STREAM_WATERMARK_UID=29b0fa37be907b876f3c5670cfaf8890
```

`settings.py` already read this variable via:

```python
CLOUDFLARE_STREAM_WATERMARK_UID = os.getenv("CLOUDFLARE_STREAM_WATERMARK_UID", "")
```

No changes to `settings.py` were required.

---

## Validation

```
GET https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/stream/watermarks
```

Result: `["29b0fa37be907b876f3c5670cfaf8890"]` — UID confirmed in list. **PASSED.**

---

## Notes

- No frontend files were changed.
- No secrets were printed, logged, or committed.
- **Existing uploaded videos will NOT automatically receive this watermark.** Videos must be re-uploaded to Cloudflare Stream with the watermark UID applied at upload time.
- The `CLOUDFLARE_STREAM_WATERMARK_UID` is already wired into the direct-upload service (`gallery/services/cloudflare_stream.py`) via `settings.CLOUDFLARE_STREAM_WATERMARK_UID`.
