"""
gallery/share_helpers.py

Pure helper functions for building Open Graph metadata and share URLs for
albums, videos, and media items.  No Django views here — only data logic.

Share URL format (served by this backend):
  /share/albums/<slug>/
  /share/videos/<pk>/
  /share/images/<pk>/

Frontend canonical URLs (on kataphotos.com):
  FRONTEND_URL/albums/<slug>
  FRONTEND_URL/videos/<pk>
  FRONTEND_URL/images/<pk>
"""

from urllib.parse import quote

from django.conf import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fb_url(share_url: str) -> str:
    """Return a Facebook sharer URL for the given share_url."""
    return (
        "https://www.facebook.com/sharer/sharer.php"
        f"?u={quote(share_url, safe='')}"
    )


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "https://kataphotos.com").rstrip("/")


def _fallback_image() -> str:
    return getattr(settings, "FALLBACK_OG_IMAGE", "")


def _bs_first(obj, field: str) -> str:
    """Return Bosnian value first, fall back to English, then legacy field."""
    bs = getattr(obj, f"{field}_bs", "") or ""
    if bs:
        return bs
    en = getattr(obj, f"{field}_en", "") or ""
    if en:
        return en
    return getattr(obj, field, "") or ""


def _truncate(text: str, length: int = 300) -> str:
    text = text.strip()
    if len(text) > length:
        return text[:length - 1] + "\u2026"
    return text


# ---------------------------------------------------------------------------
# OG image resolution
# ---------------------------------------------------------------------------

def _album_og_image(album) -> str:
    """
    Priority:
    1. album.cover_media thumbnail_url / public_url
    2. First published image MediaItem in the album
    3. First published VideoClip thumbnail in the album
    4. FALLBACK_OG_IMAGE
    """
    cover = getattr(album, "cover_media", None)
    if cover:
        url = cover.thumbnail_url or cover.public_url or ""
        if url:
            return url

    # Lazy imports to avoid circular dependency
    from .models import MediaItem, VideoClip

    first_img = (
        MediaItem.objects.filter(album=album, is_published=True, media_type="image")
        .exclude(thumbnail_url="")
        .values_list("thumbnail_url", flat=True)
        .first()
    )
    if first_img:
        return first_img

    first_vid_thumb = (
        VideoClip.objects.filter(album=album, is_public=True)
        .exclude(cloudflare_thumbnail_url="")
        .values_list("cloudflare_thumbnail_url", flat=True)
        .first()
    )
    if first_vid_thumb:
        return first_vid_thumb

    return _fallback_image()


def _video_og_image(video) -> str:
    """
    Priority:
    1. video.cloudflare_thumbnail_url
    2. Album cover thumbnail
    3. FALLBACK_OG_IMAGE
    """
    if video.cloudflare_thumbnail_url:
        return video.cloudflare_thumbnail_url

    if video.album_id:
        album = getattr(video, "album", None)
        if album:
            cover = getattr(album, "cover_media", None)
            if cover:
                url = cover.thumbnail_url or cover.public_url or ""
                if url:
                    return url

    return _fallback_image()


def _media_og_image(media_item) -> str:
    """
    Priority:
    1. media_item.thumbnail_url
    2. media_item.public_url
    3. FALLBACK_OG_IMAGE
    """
    if media_item.thumbnail_url:
        return media_item.thumbnail_url
    if media_item.public_url:
        return media_item.public_url
    return _fallback_image()


# ---------------------------------------------------------------------------
# OG metadata builders
# ---------------------------------------------------------------------------

def album_og_meta(album, request) -> dict:
    """Return an OG metadata dict for a published album."""
    share_path = f"/share/albums/{album.slug}/"
    share_url = request.build_absolute_uri(share_path)
    title = _bs_first(album, "title") or f"Album {album.pk}"
    description = _truncate(
        _bs_first(album, "description")
        or _bs_first(album, "seo_description")
        or "Pogledajte album na Kata Wild."
    )
    return {
        "og_type": "website",
        "og_title": title,
        "og_description": description,
        "og_image": _album_og_image(album),
        "og_url": share_url,
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/albums/{album.slug}",
        "is_shareable": album.is_published,
    }


def video_og_meta(video, request) -> dict:
    """Return an OG metadata dict for a public ready video."""
    from .models import VideoClip

    share_path = f"/share/videos/{video.pk}/"
    share_url = request.build_absolute_uri(share_path)
    title = _bs_first(video, "title") or f"Video {video.pk}"
    description = _truncate(
        _bs_first(video, "description")
        or "Pogledajte video na Kata Wild."
    )
    is_shareable = video.is_public and video.status == VideoClip.STATUS_READY
    return {
        "og_type": "video.other",
        "og_title": title,
        "og_description": description,
        "og_image": _video_og_image(video),
        "og_url": share_url,
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/videos/{video.pk}",
        "is_shareable": is_shareable,
    }


def media_og_meta(media_item, request) -> dict:
    """Return an OG metadata dict for a published media item (image)."""
    share_path = f"/share/images/{media_item.pk}/"
    share_url = request.build_absolute_uri(share_path)
    title = (
        _bs_first(media_item, "title")
        or _bs_first(media_item.album, "title")
        or f"Fotografija {media_item.pk}"
    )
    description = _truncate(
        _bs_first(media_item, "description")
        or _bs_first(media_item, "caption")
        or _bs_first(media_item.album, "description")
        or "Pogledajte fotografiju na Kata Wild."
    )
    return {
        "og_type": "website",
        "og_title": title,
        "og_description": description,
        "og_image": _media_og_image(media_item),
        "og_url": share_url,
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/images/{media_item.pk}",
        "is_shareable": media_item.is_published,
    }


# ---------------------------------------------------------------------------
# Lightweight share info for serializers (no DB queries beyond what's loaded)
# ---------------------------------------------------------------------------

def album_share_info(album, request) -> dict:
    """Minimal share fields for embedding in public album serializers."""
    if request is None:
        return {"share_url": "", "facebook_share_url": "", "frontend_url": "", "is_shareable": False}
    share_url = request.build_absolute_uri(f"/share/albums/{album.slug}/")
    return {
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/albums/{album.slug}",
        "is_shareable": album.is_published,
    }


def video_share_info(video, request) -> dict:
    """Minimal share fields for embedding in public video serializers."""
    from .models import VideoClip

    if request is None:
        return {"share_url": "", "facebook_share_url": "", "frontend_url": "", "is_shareable": False}
    share_url = request.build_absolute_uri(f"/share/videos/{video.pk}/")
    is_shareable = video.is_public and video.status == VideoClip.STATUS_READY
    return {
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/videos/{video.pk}",
        "is_shareable": is_shareable,
    }


def media_share_info(media_item, request) -> dict:
    """Minimal share fields for embedding in public media serializers."""
    if request is None:
        return {"share_url": "", "facebook_share_url": "", "frontend_url": "", "is_shareable": False}
    share_url = request.build_absolute_uri(f"/share/images/{media_item.pk}/")
    return {
        "share_url": share_url,
        "facebook_share_url": _fb_url(share_url),
        "frontend_url": f"{_frontend_url()}/images/{media_item.pk}",
        "is_shareable": media_item.is_published,
    }


# ---------------------------------------------------------------------------
# Crawler detection
# ---------------------------------------------------------------------------

_CRAWLER_UA_FRAGMENTS = (
    "facebookexternalhit",
    "facebot",
    "meta-externalagent",
    "twitterbot",
    "linkedinbot",
    "slackbot",
    "discordbot",
    "whatsapp",
    "telegrambot",
)


def is_social_crawler(request) -> bool:
    """Return True if the request appears to be from a social media crawler.

    Checked via case-insensitive substring match on the User-Agent header.
    When True the share view should serve the full OG HTML page.
    When False a human browser is assumed and the view should redirect.
    """
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(fragment in ua for fragment in _CRAWLER_UA_FRAGMENTS)
