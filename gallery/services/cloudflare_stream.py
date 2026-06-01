"""
Cloudflare Stream direct-upload service.

Requests a Direct Creator Upload URL from the Cloudflare Stream API and
returns the resulting video UID and upload URL.

Usage:
    from gallery.services.cloudflare_stream import create_direct_upload, CloudflareStreamUploadError

    try:
        result = create_direct_upload(
            account_id="...",
            api_token="...",
            max_duration_seconds=300,
            expiry_seconds=3600,
        )
        # result = {"uid": "...", "upload_url": "https://upload.videodelivery.net/..."}
    except CloudflareStreamUploadError as exc:
        # handle — token is never included in the message
        ...

Environment (consumed via settings, not directly here):
    CLOUDFLARE_ACCOUNT_ID                         — shared with Cloudflare Images
    CLOUDFLARE_STREAM_API_TOKEN                   — Stream-specific write token
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone


class CloudflareStreamUploadError(Exception):
    """Raised when the Cloudflare Stream API call fails for any reason."""


def create_direct_upload(
    *,
    account_id: str,
    api_token: str,
    max_duration_seconds: int,
    expiry_seconds: int,
    creator: str = "",
    meta: dict | None = None,
) -> dict:
    """
    Request a Direct Creator Upload URL from Cloudflare Stream.

    Parameters
    ----------
    account_id:           Cloudflare account ID
    api_token:            Cloudflare Stream API token (write permissions)
    max_duration_seconds: maximum allowed video duration in seconds
    expiry_seconds:       seconds until the upload URL expires
    creator:              optional creator identifier stored in Cloudflare metadata
    meta:                 optional extra metadata dict forwarded to Cloudflare

    Returns
    -------
    dict with keys:
        uid        — Cloudflare Stream video UID
        upload_url — one-time TUS upload URL for the browser/client

    Raises
    ------
    CloudflareStreamUploadError on any failure (config, network, HTTP, API)
    """
    if not account_id or not api_token:
        raise CloudflareStreamUploadError(
            "Cloudflare Stream is not configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_STREAM_API_TOKEN."
        )

    expiry_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=expiry_seconds)
    expiry_iso = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    body: dict = {
        "maxDurationSeconds": max_duration_seconds,
        "expiry": expiry_iso,
    }
    if creator:
        body["creator"] = creator
    if meta:
        body["meta"] = meta

    api_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/stream/direct_upload"
    )

    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        exc.read()  # drain the socket
        raise CloudflareStreamUploadError(
            f"Cloudflare Stream API error (HTTP {exc.code})."
        ) from exc
    except OSError as exc:
        raise CloudflareStreamUploadError(
            "Network error while reaching Cloudflare Stream API."
        ) from exc

    if not payload.get("success"):
        errors = payload.get("errors", [])
        codes = ", ".join(str(e.get("code", "")) for e in errors)
        raise CloudflareStreamUploadError(
            f"Cloudflare Stream direct-upload request failed (error codes: {codes})."
        )

    result = payload["result"]
    return {
        "uid": result["uid"],
        "upload_url": result["uploadURL"],
    }
