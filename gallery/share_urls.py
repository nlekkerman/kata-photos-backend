"""
gallery/share_urls.py

URL patterns for the public Open Graph share pages.

Mounted at /share/ in config/urls.py.
"""

from django.urls import path

from .share_views import AlbumShareView, ImageShareView, VideoShareView

urlpatterns = [
    path("albums/<slug:slug>/", AlbumShareView.as_view(), name="share-album"),
    path("videos/<int:pk>/", VideoShareView.as_view(), name="share-video"),
    path("images/<int:pk>/", ImageShareView.as_view(), name="share-image"),
]
