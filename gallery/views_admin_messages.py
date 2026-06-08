"""
Admin-only views for visitor message and video timestamp comment moderation.

Endpoints provided:
    GET  /api/gallery/admin/notifications/
    GET  /api/gallery/admin/visitor-messages/
    GET  /api/gallery/admin/video-timestamp-comments/
    PATCH /api/gallery/admin/video-timestamp-comments/<pk>/
"""

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VideoTimestampComment, VisitorMessage
from .serializers import (
    AdminVideoTimestampCommentSerializer,
    AdminVideoTimestampCommentStatusSerializer,
    AdminVisitorMessageSerializer,
    AdminVisitorMessageStatusSerializer,
)


class AdminMessagePageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ---------------------------------------------------------------------------
# Visitor messages
# ---------------------------------------------------------------------------

class AdminVisitorMessageListView(generics.ListAPIView):
    """
    GET /api/gallery/admin/visitor-messages/

    Paginated list of all VisitorMessage records for staff/admin.
    Returns newest first (model default ordering: -created_at).
    Supports optional ?status= filter.
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminVisitorMessageSerializer
    pagination_class = AdminMessagePageNumberPagination

    def get_queryset(self):
        qs = VisitorMessage.objects.select_related('video').order_by('-created_at')
        status_val = self.request.query_params.get('status', '').strip()
        if status_val:
            qs = qs.filter(status=status_val)
        return qs


# ---------------------------------------------------------------------------
# Visitor message status update
# ---------------------------------------------------------------------------

class AdminVisitorMessageDetailView(generics.GenericAPIView):
    """
    PATCH /api/gallery/admin/visitor-messages/<pk>/

    Update the status of a VisitorMessage.
    Only ``status`` is writable. Allowed values: new, read, replied, archived.
    Returns the updated message using the full admin read serializer.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['patch', 'head', 'options']
    queryset = VisitorMessage.objects.all()

    def patch(self, request, pk):
        message = generics.get_object_or_404(VisitorMessage, pk=pk)
        serializer = AdminVisitorMessageStatusSerializer(
            message, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            AdminVisitorMessageSerializer(message).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Video timestamp comments
# ---------------------------------------------------------------------------

class AdminVideoTimestampCommentListView(generics.ListAPIView):
    """
    GET /api/gallery/admin/video-timestamp-comments/

    Paginated list of all VideoTimestampComment records for admin moderation.
    Returns newest first.
    Supports optional ?status=pending|approved|rejected filter.
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminVideoTimestampCommentSerializer
    pagination_class = AdminMessagePageNumberPagination

    def get_queryset(self):
        qs = VideoTimestampComment.objects.select_related('video').order_by('-created_at')
        status_val = self.request.query_params.get('status', '').strip()
        if status_val:
            qs = qs.filter(status=status_val)
        return qs


class AdminVideoTimestampCommentDetailView(generics.GenericAPIView):
    """
    PATCH /api/gallery/admin/video-timestamp-comments/<pk>/

    Update the status of a VideoTimestampComment.
    Only ``status`` is writable. Allowed values: pending, approved, rejected.
    Returns the updated comment using the full admin read serializer.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['patch', 'head', 'options']
    queryset = VideoTimestampComment.objects.select_related('video').all()

    def patch(self, request, pk):
        comment = generics.get_object_or_404(
            VideoTimestampComment.objects.select_related('video'), pk=pk
        )
        serializer = AdminVideoTimestampCommentStatusSerializer(
            comment, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            AdminVideoTimestampCommentSerializer(comment).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Notification counts
# ---------------------------------------------------------------------------

class AdminNotificationCountsView(APIView):
    """
    GET /api/gallery/admin/notifications/

    Returns aggregate counts for admin UI notification badges.
    Staff/admin only. Never exposes message or comment content.

    Response shape:
        {
            "new_messages_count": <int>,
            "pending_comments_count": <int>,
            "total_count": <int>,
            "has_notifications": <bool>
        }

    Counting rules:
        new_messages_count   — VisitorMessage records where status == STATUS_NEW ('new')
        pending_comments_count — VideoTimestampComment records where status == STATUS_PENDING ('pending')
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        new_messages = VisitorMessage.objects.filter(
            status=VisitorMessage.STATUS_NEW
        ).count()
        pending_comments = VideoTimestampComment.objects.filter(
            status=VideoTimestampComment.STATUS_PENDING
        ).count()
        total = new_messages + pending_comments
        return Response({
            'new_messages_count': new_messages,
            'pending_comments_count': pending_comments,
            'total_count': total,
            'has_notifications': total > 0,
        })
