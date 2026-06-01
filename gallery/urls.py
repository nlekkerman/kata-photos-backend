from django.urls import path

from .views import (
    AdminImageGalleryListCreateView,
    AdminImageGalleryRetrieveUpdateDestroyView,
    AdminImageItemListCreateView,
    AdminImageItemRetrieveUpdateDestroyView,
    AdminVideoCompleteUploadView,
    AdminVideoDirectUploadView,
    AdminVideoGalleryListCreateView,
    AdminVideoGalleryRetrieveUpdateDestroyView,
    AdminVideoItemListView,
    AdminVideoItemRetrieveUpdateDestroyView,
    AdminVideoRefreshStatusView,
    AlbumCoverUpdateView,
    AlbumListCreateView,
    AlbumMediaListCreateView,
    AlbumRetrieveUpdateDestroyView,
    FieldNoteDetailView,
    FieldNoteListView,
    MediaItemRetrieveUpdateDestroyView,
    VideoClipDetailView,
    VideoClipDirectUploadView,
    VideoClipListView,
    VideoClipSyncView,
)

urlpatterns = [
    # ------------------------------------------------------------------
    # Public / legacy endpoints (unchanged)
    # ------------------------------------------------------------------
    path('albums/', AlbumListCreateView.as_view(), name='album-list'),
    path('albums/<slug:slug>/', AlbumRetrieveUpdateDestroyView.as_view(), name='album-detail'),
    path('albums/<slug:slug>/cover/', AlbumCoverUpdateView.as_view(), name='album-cover'),
    path('albums/<slug:slug>/media/', AlbumMediaListCreateView.as_view(), name='album-media-list'),
    path('media/<int:pk>/', MediaItemRetrieveUpdateDestroyView.as_view(), name='mediaitem-detail'),
    path('field-notes/', FieldNoteListView.as_view(), name='fieldnote-list'),
    path('field-notes/<slug:slug>/', FieldNoteDetailView.as_view(), name='fieldnote-detail'),
    path('videos/', VideoClipListView.as_view(), name='videoclip-list'),
    path('videos/direct-upload/', VideoClipDirectUploadView.as_view(), name='videoclip-direct-upload'),
    path('videos/<int:pk>/', VideoClipDetailView.as_view(), name='videoclip-detail'),
    path('videos/<int:pk>/sync/', VideoClipSyncView.as_view(), name='videoclip-sync'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — image galleries
    # ------------------------------------------------------------------
    path('admin/image-galleries/', AdminImageGalleryListCreateView.as_view(), name='admin-image-gallery-list'),
    path('admin/image-galleries/<int:pk>/', AdminImageGalleryRetrieveUpdateDestroyView.as_view(), name='admin-image-gallery-detail'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — image items
    # ------------------------------------------------------------------
    path('admin/images/', AdminImageItemListCreateView.as_view(), name='admin-image-list'),
    path('admin/images/<int:pk>/', AdminImageItemRetrieveUpdateDestroyView.as_view(), name='admin-image-detail'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — video galleries
    # ------------------------------------------------------------------
    path('admin/video-galleries/', AdminVideoGalleryListCreateView.as_view(), name='admin-video-gallery-list'),
    path('admin/video-galleries/<int:pk>/', AdminVideoGalleryRetrieveUpdateDestroyView.as_view(), name='admin-video-gallery-detail'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — video items
    # NOTE: fixed-path segments (direct-upload, complete-upload) must
    # come before the <int:pk> pattern to avoid routing ambiguity.
    # ------------------------------------------------------------------
    path('admin/videos/', AdminVideoItemListView.as_view(), name='admin-video-list'),
    path('admin/videos/direct-upload/', AdminVideoDirectUploadView.as_view(), name='admin-video-direct-upload'),
    path('admin/videos/complete-upload/', AdminVideoCompleteUploadView.as_view(), name='admin-video-complete-upload'),
    path('admin/videos/<int:pk>/', AdminVideoItemRetrieveUpdateDestroyView.as_view(), name='admin-video-detail'),
    path('admin/videos/<int:pk>/refresh-status/', AdminVideoRefreshStatusView.as_view(), name='admin-video-refresh-status'),
]
