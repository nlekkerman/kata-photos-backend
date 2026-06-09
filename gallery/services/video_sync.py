"""
Video sync service: apply a Cloudflare Stream API response to a VideoClip record.

Exposes:
    sync_video_from_cloudflare(video, cf, *, customer_subdomain) -> list[str]
        Updates video fields from the Cloudflare Stream video-details dict.
        Does NOT call video.save() — caller must call video.save(update_fields=...).
        Returns the list of field names that were modified (may be empty).

Constants:
    STUCK_PROCESSING_THRESHOLD  — timedelta after which a non-terminal video is
                                  considered stuck and gets a processing_warning.
"""
import logging
from datetime import timedelta

from django.utils import timezone as dj_timezone

from .cloudflare_stream import build_playback_url, build_thumbnail_url, map_cloudflare_status

logger = logging.getLogger(__name__)

# Videos that stay in a non-terminal state beyond this threshold get a warning.
STUCK_PROCESSING_THRESHOLD = timedelta(minutes=30)

_STUCK_WARNING = (
    "Still processing after 30 minutes. "
    "Check Cloudflare Stream status or source video codec."
)


def sync_video_from_cloudflare(video, cf: dict, *, customer_subdomain: str) -> list[str]:
    """
    Apply a Cloudflare Stream video-details response dict to *video*.

    Fields updated (when changed):
        status, is_public, duration_seconds,
        cloudflare_playback_url, cloudflare_thumbnail_url,
        cloudflare_status_state, cloudflare_status_step, cloudflare_pct_complete,
        cloudflare_error_reason_code, cloudflare_error_reason_text,
        cloudflare_last_synced_at, processing_warning.

    Does not save — caller must call video.save(update_fields=returned_list).
    Returns the list of updated field names (may be empty).
    """
    # Local import avoids circular dependency at module load time.
    from gallery.models import VideoClip  # noqa: PLC0415

    update_fields: list[str] = []
    now = dj_timezone.now()

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    new_status = map_cloudflare_status(cf)
    if video.status != new_status:
        video.status = new_status
        update_fields.append('status')
        logger.info(
            "video_sync: cf_uid=%r pk=%s status→%r",
            video.cloudflare_uid, video.pk, new_status,
        )

    # Failed videos must not remain publicly visible.
    if new_status == VideoClip.STATUS_FAILED and video.is_public:
        video.is_public = False
        update_fields.append('is_public')

    # -------------------------------------------------------------------------
    # Duration
    # -------------------------------------------------------------------------
    raw_duration = cf.get('duration')
    if raw_duration is not None and raw_duration >= 0:
        new_duration = round(raw_duration)
        if video.duration_seconds != new_duration:
            video.duration_seconds = new_duration
            update_fields.append('duration_seconds')

    # -------------------------------------------------------------------------
    # Playback / thumbnail URLs
    # -------------------------------------------------------------------------
    if customer_subdomain:
        new_playback = build_playback_url(
            customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
        )
        if video.cloudflare_playback_url != new_playback:
            video.cloudflare_playback_url = new_playback
            update_fields.append('cloudflare_playback_url')

        new_thumbnail = build_thumbnail_url(
            customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
        )
        if video.cloudflare_thumbnail_url != new_thumbnail:
            video.cloudflare_thumbnail_url = new_thumbnail
            update_fields.append('cloudflare_thumbnail_url')

    # -------------------------------------------------------------------------
    # Cloudflare status audit fields
    # -------------------------------------------------------------------------
    cf_status_obj = cf.get('status') or {}
    state = cf_status_obj.get('state') or ''
    step = cf_status_obj.get('step') or ''
    pct = str(cf_status_obj.get('pctComplete') or '')
    err_code = cf_status_obj.get('errorReasonCode') or ''
    err_text = cf_status_obj.get('errorReasonText') or ''

    for attr, val in (
        ('cloudflare_status_state', state),
        ('cloudflare_status_step', step),
        ('cloudflare_pct_complete', pct),
        ('cloudflare_error_reason_code', err_code),
        ('cloudflare_error_reason_text', err_text),
    ):
        if getattr(video, attr) != val:
            setattr(video, attr, val)
            update_fields.append(attr)

    # Always stamp the sync time.
    video.cloudflare_last_synced_at = now
    update_fields.append('cloudflare_last_synced_at')

    # Structured logging for notable states.
    if state == 'error':
        logger.warning(
            "video_sync: cf_uid=%r pk=%s Cloudflare error code=%r text=%r",
            video.cloudflare_uid, video.pk, err_code, err_text,
        )
    elif new_status == VideoClip.STATUS_READY:
        logger.info(
            "video_sync: cf_uid=%r pk=%s Cloudflare sync success — ready",
            video.cloudflare_uid, video.pk,
        )
    else:
        logger.info(
            "video_sync: cf_uid=%r pk=%s Cloudflare state=%r pct=%r",
            video.cloudflare_uid, video.pk, state, pct,
        )

    # -------------------------------------------------------------------------
    # Stuck processing detection
    # -------------------------------------------------------------------------
    terminal_statuses = {VideoClip.STATUS_READY, VideoClip.STATUS_FAILED}
    if new_status not in terminal_statuses and video.processing_started_at:
        elapsed = now - video.processing_started_at
        if elapsed >= STUCK_PROCESSING_THRESHOLD and video.processing_warning != _STUCK_WARNING:
            video.processing_warning = _STUCK_WARNING
            update_fields.append('processing_warning')
            logger.warning(
                "video_sync: cf_uid=%r pk=%s stuck in %r after %s — warning set",
                video.cloudflare_uid, video.pk, new_status, elapsed,
            )
    elif new_status in terminal_statuses and video.processing_warning:
        # Clear stale warning once terminal state is reached.
        video.processing_warning = ''
        update_fields.append('processing_warning')

    return update_fields
