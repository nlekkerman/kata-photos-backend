from django.urls import path

from .views import (
    AlbumCoverUpdateView,
    AlbumListCreateView,
    AlbumMediaListCreateView,
    AlbumRetrieveUpdateDestroyView,
    FieldNoteDetailView,
    FieldNoteListView,
    MediaItemRetrieveUpdateDestroyView,
    VideoClipDirectUploadView,
)

urlpatterns = [
    path('albums/', AlbumListCreateView.as_view(), name='album-list'),
    path('albums/<slug:slug>/', AlbumRetrieveUpdateDestroyView.as_view(), name='album-detail'),
    path('albums/<slug:slug>/cover/', AlbumCoverUpdateView.as_view(), name='album-cover'),
    path('albums/<slug:slug>/media/', AlbumMediaListCreateView.as_view(), name='album-media-list'),
    path('media/<int:pk>/', MediaItemRetrieveUpdateDestroyView.as_view(), name='mediaitem-detail'),
    path('field-notes/', FieldNoteListView.as_view(), name='fieldnote-list'),
    path('field-notes/<slug:slug>/', FieldNoteDetailView.as_view(), name='fieldnote-detail'),
    path('videos/direct-upload/', VideoClipDirectUploadView.as_view(), name='videoclip-direct-upload'),
]
