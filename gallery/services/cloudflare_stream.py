"""
Cloudflare Stream service: direct uploads, video details, and URL helpers.

Usage:
    from gallery.services.cloudflare_stream import (
        create_direct_upload,
        get_video_details,
        list_videos,
        map_cloudflare_status,
        build_playback_url,
        build_thumbnail_url,
        CloudflareStreamError,
    )

Environment (consumed via settings, not directly here):
    CLOUDFLARE_ACCOUNT_ID                          — shared with Cloudflare Images
    CLOUDFLARE_STREAM_API_TOKEN                    — Stream-specific write token
    CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN           — e.g. customer-abc123.cloudflarestream.com
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
"""
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_CF_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


class CloudflareStreamError(Exception):
    """Raised when any Cloudflare Stream API call fails."""


# Backward-compat alias used by existing code.
CloudflareStreamUploadError = CloudflareStreamError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_get(api_url: str, api_token: str, timeout: int = 30) -> dict:
    """GET a Cloudflare API endpoint and return the parsed JSON body.

    Raises CloudflareStreamError on HTTP or network failure.
    The API token is never included in raised exception messages.
    """
    req = urllib.request.Request(
        api_url,
        headers={"Authorization": f"Bearer {api_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        logger.error(
            "Cloudflare Stream API HTTP error: status=%s url=%s response_body=%r",
            exc.code,
            api_url,
            error_body[:1000],
        )
        raise CloudflareStreamError(
            f"Cloudflare Stream API error (HTTP {exc.code})."
        ) from exc
    except OSError as exc:
        logger.error("Cloudflare Stream network error: url=%s exc=%r", api_url, exc)
        raise CloudflareStreamError(
            "Network error while reaching Cloudflare Stream API."
        ) from exc


def _check_configured(account_id: str, api_token: str) -> None:
    if not account_id or not api_token:
        raise CloudflareStreamError(
            "Cloudflare Stream is not configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_STREAM_API_TOKEN."
        )


# ---------------------------------------------------------------------------
# Public URL helpers
# ---------------------------------------------------------------------------

def build_playback_url(*, customer_subdomain: str, uid: str) -> str:
    """Return the Cloudflare Stream iframe embed URL for *uid*.

    Format: ``https://{customer_subdomain}/{uid}/iframe``
    """
    return f"https://{customer_subdomain}/{uid}/iframe"


def build_thumbnail_url(*, customer_subdomain: str, uid: str) -> str:
    """Return the Cloudflare Stream default thumbnail URL for *uid*.

    Format: ``https://{customer_subdomain}/{uid}/thumbnails/thumbnail.jpg``
    This matches the pattern documented at
    https://developers.cloudflare.com/stream/viewing-videos/displaying-thumbnails/
    """
    return f"https://{customer_subdomain}/{uid}/thumbnails/thumbnail.jpg"


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

def map_cloudflare_status(cf_result: dict) -> str:
    """Map a Cloudflare Stream video result dict to a local VideoClip status string.

    Cloudflare ``status.state`` values (documented):
        pendingupload — file not yet received
        inprogress    — transcoding/processing
        ready         — playable
        error         — transcoding failed

    Both ``readyToStream`` AND ``status.state == "ready"`` must be true before
    we consider the video ready.  Cloudflare sets ``readyToStream=True`` (making
    the thumbnail available) before all encoding variants / DASH manifests are
    complete, so checking ``readyToStream`` alone causes the manifest endpoint
    to return 500 while playback is still pending.

    Returns one of: ``"ready"``, ``"processing"``, ``"failed"``.
    Never returns ``"uploading"`` — that state is set only at creation time.
    """
    state: str = (cf_result.get("status") or {}).get("state", "")
    if state == "error":
        return "failed"
    if cf_result.get("readyToStream") and state == "ready":
        return "ready"
    # pendingupload, inprogress, readyToStream-without-confirmed-state, or unknown
    return "processing"


def create_direct_upload(
    *,
    account_id: str,
    api_token: str,
    max_duration_seconds: int,
    expiry_seconds: int,
    creator: str = "",
    meta: dict | None = None,
    watermark_uid: str = "",
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
    watermark_uid:        optional Cloudflare Stream watermark profile UID;
                          when non-empty the watermark is burned into the video

    Returns
    -------
    dict with keys:
        uid        — Cloudflare Stream video UID
        upload_url — one-time TUS upload URL for the browser/client

    Raises
    ------
    CloudflareStreamError on any failure (config, network, HTTP, API)
    """
    _check_configured(account_id, api_token)
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
    if watermark_uid:
        body["watermark"] = {"uid": watermark_uid}

    api_url = f"{_CF_API_BASE}/{account_id}/stream/direct_upload"

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
        error_body = exc.read().decode(errors="replace")
        logger.error(
            "Cloudflare Stream API HTTP error: status=%s url=%s response_body=%r",
            exc.code,
            api_url,
            error_body[:1000],
        )
        raise CloudflareStreamError(
            f"Cloudflare Stream API error (HTTP {exc.code})."
        ) from exc
    except OSError as exc:
        logger.error("Cloudflare Stream network error: url=%s exc=%r", api_url, exc)
        raise CloudflareStreamError(
            "Network error while reaching Cloudflare Stream API."
        ) from exc

    if not payload.get("success"):
        errors = payload.get("errors", [])
        codes = ", ".join(str(e.get("code", "")) for e in errors)
        logger.error(
            "Cloudflare Stream API non-success: url=%s errors=%r",
            api_url,
            errors,
        )
        raise CloudflareStreamError(
            f"Cloudflare Stream direct-upload request failed (error codes: {codes})."
        )

    result = payload["result"]
    return {
        "uid": result["uid"],
        "upload_url": result["uploadURL"],
    }


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

def get_video_details(
    *,
    account_id: str,
    api_token: str,
    uid: str,
) -> dict:
    """Fetch details for a single video from Cloudflare Stream.

    Returns the ``result`` dict from the Cloudflare API response, which
    contains fields such as ``readyToStream``, ``status``, ``duration``,
    ``thumbnail``, and ``meta``.

    Raises
    ------
    CloudflareStreamError on any failure.
    """
    _check_configured(account_id, api_token)
    api_url = f"{_CF_API_BASE}/{account_id}/stream/{uid}"
    payload = _safe_get(api_url, api_token)

    if not payload.get("success"):
        errors = payload.get("errors", [])
        codes = ", ".join(str(e.get("code", "")) for e in errors)
        logger.error(
            "Cloudflare Stream API non-success: url=%s errors=%r", api_url, errors
        )
        raise CloudflareStreamError(
            f"Cloudflare Stream video-details request failed (error codes: {codes})."
        )

    return payload["result"]


def list_videos(
    *,
    account_id: str,
    api_token: str,
) -> list[dict]:
    """List all videos in the Cloudflare Stream account.

    Returns a list of video result dicts (same shape as ``get_video_details``).

    Raises
    ------
    CloudflareStreamError on any failure.
    """
    _check_configured(account_id, api_token)
    api_url = f"{_CF_API_BASE}/{account_id}/stream"
    payload = _safe_get(api_url, api_token)

    if not payload.get("success"):
        errors = payload.get("errors", [])
        codes = ", ".join(str(e.get("code", "")) for e in errors)
        logger.error(
            "Cloudflare Stream API non-success: url=%s errors=%r", api_url, errors
        )
        raise CloudflareStreamError(
            f"Cloudflare Stream list-videos request failed (error codes: {codes})."
        )

    return payload.get("result", [])
