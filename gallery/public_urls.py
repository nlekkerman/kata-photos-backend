from django.urls import path

from .views import (
    HeroVideoView,
    PublicVideoDetailView,
    PublicVideoListView,
    VideoTimestampCommentListCreateView,
    VisitorMessageCreateView,
)

urlpatterns = [
    path('hero-video/', HeroVideoView.as_view(), name='hero-video'),
    path('messages/', VisitorMessageCreateView.as_view(), name='visitor-message-create'),
    path('videos/', PublicVideoListView.as_view(), name='public-video-list'),
    path('videos/<int:pk>/', PublicVideoDetailView.as_view(), name='public-video-detail'),
    path('videos/<int:video_pk>/comments/', VideoTimestampCommentListCreateView.as_view(), name='video-comment-list-create'),
]
