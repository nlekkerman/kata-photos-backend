from typing import Optional

from django.db.models import Q, QuerySet

from gallery.models import VideoClip


def get_public_ready_video_queryset() -> QuerySet[VideoClip]:
    """
    Canonical public-ready video queryset.

    MVP scope:
    - Only includes videos safe for public visitors.
    - Excludes private, uploading, processing, failed, and unpublished videos.
    - Uses the same newest-first ordering as the public video list cursor.
    """
    return (
        VideoClip.objects
        .filter(is_public=True, status=VideoClip.STATUS_READY)
        .select_related("album")
        .order_by("-created_at", "-id")
    )


def get_public_ready_gallery_video_queryset(video: VideoClip) -> QuerySet[VideoClip]:
    """
    Return public-ready videos from the same gallery/album as the current video.

    This prevents previous/next navigation from jumping across unrelated galleries.
    """
    return get_public_ready_video_queryset().filter(album_id=video.album_id)


def get_previous_public_video(video: VideoClip) -> Optional[VideoClip]:
    """
    Return the newer public-ready video before the current video in the same gallery.

    Public gallery order is newest-first: -created_at, -id.
    Therefore "previous" means the item above current in that gallery list.
    """
    return (
        get_public_ready_gallery_video_queryset(video)
        .filter(
            Q(created_at__gt=video.created_at)
            | Q(created_at=video.created_at, id__gt=video.id)
        )
        .order_by("created_at", "id")
        .first()
    )


def get_next_public_video(video: VideoClip) -> Optional[VideoClip]:
    """
    Return the older public-ready video after the current video in the same gallery.

    Public gallery order is newest-first: -created_at, -id.
    Therefore "next" means the item below current in that gallery list.
    """
    return (
        get_public_ready_gallery_video_queryset(video)
        .filter(
            Q(created_at__lt=video.created_at)
            | Q(created_at=video.created_at, id__lt=video.id)
        )
        .order_by("-created_at", "-id")
        .first()
    )


def serialize_public_video_nav_item(video: Optional[VideoClip], *, lang: str) -> Optional[dict]:
    """
    Shape a minimal navigation item for the public video detail response.

    Keeps navigation payload small and public-safe.
    """
    if video is None:
        return None

    title = (
        video.title_bs
        if lang == "bs"
        else video.title_en
    ) or video.title_bs or video.title_en or ""

    return {
        "id": video.id,
        "title": title,
        "title_bs": video.title_bs,
        "title_en": video.title_en,
        "cloudflare_thumbnail_url": video.cloudflare_thumbnail_url,
        "album_id": video.album_id,
    }


def get_public_video_navigation(video: VideoClip, *, lang: str) -> dict:
    """
    Return public-safe previous/next navigation inside the current video's gallery.
    """
    previous_video = get_previous_public_video(video)
    next_video = get_next_public_video(video)

    return {
        "previous_video": serialize_public_video_nav_item(previous_video, lang=lang),
        "next_video": serialize_public_video_nav_item(next_video, lang=lang),
    }