"""
gallery/share_views.py

Public HTML share pages for albums, videos, and media items.

Routes (mounted at /share/):
  /share/albums/<slug>/
  /share/videos/<pk>/
  /share/images/<pk>/

Each view renders a minimal HTML page with correct Open Graph meta tags so
Facebook's crawler can build a rich preview.  The page also contains a
visible fallback with a link to the real frontend page on kataphotos.com.

Rules:
- Private/unpublished/unready content → 404 (no metadata exposed).
- No auto-redirect — Facebook must be able to scrape the page.
- No authentication required — pages are fully public.
"""

import html
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.views import View

from .models import Album, MediaItem, VideoClip
from .share_helpers import album_og_meta, is_social_crawler, media_og_meta, video_og_meta

# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="bs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Kata Wild</title>

<!-- Open Graph -->
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Kata Wild">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<meta property="og:image" content="{og_image}">
<meta property="og:url" content="{og_url}">

<!-- Twitter / X card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_description}">
<meta name="twitter:image" content="{og_image}">

<style>
  body {{
    font-family: system-ui, sans-serif;
    max-width: 640px;
    margin: 48px auto;
    padding: 0 20px;
    color: #1a1a1a;
    background: #fafafa;
  }}
  img.preview {{
    width: 100%;
    border-radius: 10px;
    margin-bottom: 20px;
    display: block;
  }}
  h1 {{ font-size: 1.5rem; margin: 0 0 12px; }}
  p.desc {{ color: #444; line-height: 1.6; margin: 0 0 24px; }}
  a.cta {{
    display: inline-block;
    padding: 12px 28px;
    background: #1c5e28;
    color: #fff;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 600;
  }}
  a.cta:hover {{ background: #14471e; }}
</style>
</head>
<body>
{image_tag}
<h1>{title}</h1>
<p class="desc">{description}</p>
<a class="cta" href="{frontend_url}" rel="noopener noreferrer">
  Pogledaj na Kata Wild &rarr;
</a>
</body>
</html>"""


def _e(value: str) -> str:
    """HTML-escape a string for safe insertion into attribute values or text."""
    return html.escape(str(value), quote=True)


def _render(og: dict) -> HttpResponse:
    image_tag = ""
    if og.get("og_image"):
        image_tag = (
            f'<img class="preview" src="{_e(og["og_image"])}"'
            f' alt="{_e(og["og_title"])}">'
        )
    body = _HTML_TEMPLATE.format(
        og_type=_e(og.get("og_type", "website")),
        og_title=_e(og["og_title"]),
        og_description=_e(og["og_description"]),
        og_image=_e(og.get("og_image", "")),
        og_url=_e(og["og_url"]),
        title=_e(og["og_title"]),
        description=_e(og["og_description"]),
        frontend_url=_e(og["frontend_url"]),
        image_tag=image_tag,
    )
    return HttpResponse(body, content_type="text/html; charset=utf-8")


def _build_redirect_url(frontend_url: str, extra_params: dict) -> str:
    """Append extra_params to frontend_url, preserving any existing query params.

    Params already present in the URL are not overwritten or duplicated.
    """
    parsed = urlparse(frontend_url)
    existing = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in extra_params.items():
        if key not in existing:
            existing[key] = [value]
    new_query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AlbumShareView(View):
    """
    GET /share/albums/<slug>/

    Renders an OG-tagged HTML page for a published album.
    Returns 404 for unpublished or missing albums.
    """

    def get(self, request, slug):
        try:
            album = (
                Album.objects
                .select_related("cover_media")
                .get(slug=slug, is_published=True)
            )
        except Album.DoesNotExist:
            raise Http404("Album not found or not public.")
        og = album_og_meta(album, request)
        if not is_social_crawler(request):
            redirect_url = _build_redirect_url(
                og["frontend_url"],
                {"utm_source": "facebook", "utm_medium": "social"},
            )
            return HttpResponseRedirect(redirect_url)
        return _render(og)


class VideoShareView(View):
    """
    GET /share/videos/<pk>/

    Renders an OG-tagged HTML page for a public, ready video.
    Returns 404 for private, uploading, processing, failed, or missing videos.
    """

    def get(self, request, pk):
        try:
            video = (
                VideoClip.objects
                .select_related("album__cover_media")
                .get(pk=pk, is_public=True, status=VideoClip.STATUS_READY)
            )
        except VideoClip.DoesNotExist:
            raise Http404("Video not found or not public.")
        og = video_og_meta(video, request)
        if not is_social_crawler(request):
            redirect_url = _build_redirect_url(
                og["frontend_url"],
                {"utm_source": "facebook", "utm_medium": "social", "autoplay": "1"},
            )
            return HttpResponseRedirect(redirect_url)
        return _render(og)


class ImageShareView(View):
    """
    GET /share/images/<pk>/

    Renders an OG-tagged HTML page for a published media item (image).
    Returns 404 for unpublished or missing items.
    """

    def get(self, request, pk):
        try:
            media_item = (
                MediaItem.objects
                .select_related("album")
                .get(pk=pk, is_published=True, media_type="image")
            )
        except MediaItem.DoesNotExist:
            raise Http404("Image not found or not public.")
        og = media_og_meta(media_item, request)
        if not is_social_crawler(request):
            redirect_url = _build_redirect_url(
                og["frontend_url"],
                {"utm_source": "facebook", "utm_medium": "social"},
            )
            return HttpResponseRedirect(redirect_url)
        return _render(og)
