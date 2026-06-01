"""
Cloudflare Images upload service.

Uploads an image file to Cloudflare Images API and returns the resulting
Cloudflare image ID and variant URLs.

Usage:
    from gallery.services.cloudflare_images import upload_image, CloudflareUploadError

    try:
        result = upload_image(
            file_bytes,
            filename="photo.jpg",
            content_type="image/jpeg",
        )
        # result = {"cf_id": "...", "public_url": "https://imagedelivery.net/...", "thumbnail_url": "..."}
    except CloudflareUploadError as exc:
        # handle error — do not surface Cloudflare token in the exception message
        ...

Environment:
    CLOUDFLARE_ACCOUNT_ID        — Cloudflare account ID (not the hash, the numeric-ish ID)
    CLOUDFLARE_IMAGES_API_TOKEN  — API token with Cloudflare Images write permissions
"""
import json
import os
import urllib.error
import urllib.request
import uuid


class CloudflareUploadError(Exception):
    """Raised when the Cloudflare Images API call fails for any reason."""


def upload_image(
    file_bytes: bytes,
    *,
    filename: str,
    content_type: str,
    account_id: str = "",
    api_token: str = "",
) -> dict:
    """
    Upload raw image bytes to Cloudflare Images.

    Parameters
    ----------
    file_bytes:   raw bytes of the image file
    filename:     original filename (used as Content-Disposition filename)
    content_type: MIME type, e.g. "image/jpeg"
    account_id:   Cloudflare account ID — falls back to settings if empty
    api_token:    Cloudflare Images API token — falls back to settings if empty

    Returns
    -------
    dict with keys:
        cf_id        — Cloudflare image ID
        public_url   — first variant URL returned by Cloudflare
        thumbnail_url — smaller-variant URL if available, otherwise same as public_url

    Raises
    ------
    CloudflareUploadError on any failure (network, HTTP error, API error)
    """
    from django.conf import settings as django_settings

    account_id = account_id or django_settings.CLOUDFLARE_ACCOUNT_ID
    api_token = api_token or django_settings.CLOUDFLARE_IMAGES_API_TOKEN

    if not account_id or not api_token:
        raise CloudflareUploadError(
            "Cloudflare Images is not configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_IMAGES_API_TOKEN."
        )

    api_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1"
    )
    safe_name = _safe_filename(filename)
    boundary = uuid.uuid4().hex

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        raise CloudflareUploadError(
            f"Cloudflare Images API error (HTTP {exc.code})."
        ) from exc
    except OSError as exc:
        raise CloudflareUploadError(
            "Network error while reaching Cloudflare Images API."
        ) from exc

    if not payload.get("success"):
        errors = payload.get("errors", [])
        codes = ", ".join(str(e.get("code", "")) for e in errors)
        raise CloudflareUploadError(
            f"Cloudflare Images upload failed (error codes: {codes})."
        )

    result = payload["result"]
    cf_id: str = result["id"]
    variants: list = result.get("variants", [])

    public_url = variants[0] if variants else ""
    thumbnail_url = next(
        (v for v in variants if "/thumbnail" in v or "/small" in v),
        public_url,
    )

    return {
        "cf_id": cf_id,
        "public_url": public_url,
        "thumbnail_url": thumbnail_url,
    }


def _safe_filename(filename: str) -> str:
    """Return a plain ASCII basename safe for use in a Content-Disposition header."""
    name = os.path.basename(filename or "image")
    return name.encode("ascii", errors="replace").decode()
