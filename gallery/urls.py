from django.urls import path

from .views import AlbumDetailView, AlbumListView, AlbumMediaListView, MediaItemDetailView

urlpatterns = [
    path('albums/', AlbumListView.as_view(), name='album-list'),
    path('albums/<slug:slug>/', AlbumDetailView.as_view(), name='album-detail'),
    path('albums/<slug:slug>/media/', AlbumMediaListView.as_view(), name='album-media-list'),
    path('media/<int:pk>/', MediaItemDetailView.as_view(), name='mediaitem-detail'),
]
