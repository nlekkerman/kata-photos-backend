from django.urls import path

from .views_admin_messages import (
    AdminMarkNotificationsSeenView,
    AdminNotificationCountsView,
    AdminVideoTimestampCommentDetailView,
    AdminVideoTimestampCommentListView,
    AdminVisitorMessageDetailView,
    AdminVisitorMessageListView,
)
from .views import (
    AdminImageGalleryListCreateView,
    AdminImageGalleryRetrieveUpdateDestroyView,
    AdminImageItemListCreateView,
    AdminImageItemRetrieveUpdateDestroyView,
    AdminTagListCreateView,
    AdminTagRetrieveUpdateDestroyView,
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
    VisitorMessageReplyView,
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
    # Admin-only endpoints — tags
    # ------------------------------------------------------------------
    path('admin/tags/', AdminTagListCreateView.as_view(), name='admin-tag-list'),
    path('admin/tags/<int:pk>/', AdminTagRetrieveUpdateDestroyView.as_view(), name='admin-tag-detail'),

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

    # ------------------------------------------------------------------
    # Admin-only endpoints — notification counts
    # NOTE: mark-seen fixed path must come before the bare notifications/ path.
    # ------------------------------------------------------------------
    path('admin/notifications/mark-seen/', AdminMarkNotificationsSeenView.as_view(), name='admin-notifications-mark-seen'),
    path('admin/notifications/', AdminNotificationCountsView.as_view(), name='admin-notifications'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — visitor messages
    # ------------------------------------------------------------------
    path('admin/visitor-messages/', AdminVisitorMessageListView.as_view(), name='admin-visitor-message-list'),
    path('admin/visitor-messages/<int:pk>/', AdminVisitorMessageDetailView.as_view(), name='admin-visitor-message-detail'),
    path('admin/visitor-messages/<int:pk>/reply/', VisitorMessageReplyView.as_view(), name='admin-visitor-message-reply'),

    # ------------------------------------------------------------------
    # Admin-only endpoints — video timestamp comments
    # ------------------------------------------------------------------
    path('admin/video-timestamp-comments/', AdminVideoTimestampCommentListView.as_view(), name='admin-video-timestamp-comment-list'),
    path('admin/video-timestamp-comments/<int:pk>/', AdminVideoTimestampCommentDetailView.as_view(), name='admin-video-timestamp-comment-detail'),
]
