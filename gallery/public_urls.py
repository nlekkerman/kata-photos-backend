from django.urls import path

from .views import HeroVideoView

urlpatterns = [
    path('hero-video/', HeroVideoView.as_view(), name='hero-video'),
]
