from django.urls import path

from .views import (
    HeroVideoView,
    PublicAlbumDetailView,
    PublicAlbumListView,
    PublicAlbumMediaView,
    PublicAlbumVideosView,
    PublicVideoDetailView,
    PublicVideoListView,
    VideoTimestampCommentListCreateView,
    VisitorMessageCreateView,
)
from .views_analytics import PublicAnalyticsEventView

urlpatterns = [
    path('hero-video/', HeroVideoView.as_view(), name='hero-video'),
    path('messages/', VisitorMessageCreateView.as_view(), name='visitor-message-create'),
    path('videos/', PublicVideoListView.as_view(), name='public-video-list'),
    path('videos/<int:pk>/', PublicVideoDetailView.as_view(), name='public-video-detail'),
    path('videos/<int:video_pk>/comments/', VideoTimestampCommentListCreateView.as_view(), name='video-comment-list-create'),
    path('albums/', PublicAlbumListView.as_view(), name='public-album-list'),
    path('albums/<slug:slug>/', PublicAlbumDetailView.as_view(), name='public-album-detail'),
    path('albums/<slug:slug>/videos/', PublicAlbumVideosView.as_view(), name='public-album-videos'),
    path('albums/<slug:slug>/media/', PublicAlbumMediaView.as_view(), name='public-album-media'),
    path('analytics/events/', PublicAnalyticsEventView.as_view(), name='public-analytics-event'),
]
