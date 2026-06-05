from django.urls import path

from .views import HeroVideoView, VisitorMessageCreateView

urlpatterns = [
    path('hero-video/', HeroVideoView.as_view(), name='hero-video'),
    path('messages/', VisitorMessageCreateView.as_view(), name='visitor-message-create'),
]
