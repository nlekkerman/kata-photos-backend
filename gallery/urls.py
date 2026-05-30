from django.urls import path

from .views import (
    AlbumDetailView,
    AlbumListView,
    AlbumMediaListView,
    FieldNoteDetailView,
    FieldNoteListView,
    MediaItemDetailView,
)

urlpatterns = [
    path('albums/', AlbumListView.as_view(), name='album-list'),
    path('albums/<slug:slug>/', AlbumDetailView.as_view(), name='album-detail'),
    path('albums/<slug:slug>/media/', AlbumMediaListView.as_view(), name='album-media-list'),
    path('media/<int:pk>/', MediaItemDetailView.as_view(), name='mediaitem-detail'),
    path('field-notes/', FieldNoteListView.as_view(), name='fieldnote-list'),
    path('field-notes/<slug:slug>/', FieldNoteDetailView.as_view(), name='fieldnote-detail'),
]
