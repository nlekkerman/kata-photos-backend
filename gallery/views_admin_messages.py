"""
Admin-only views for visitor message and video timestamp comment moderation.

Endpoints provided:
    GET  /api/gallery/admin/visitor-messages/
    GET  /api/gallery/admin/video-timestamp-comments/
    PATCH /api/gallery/admin/video-timestamp-comments/<pk>/
"""

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import VideoTimestampComment, VisitorMessage
from .serializers import (
    AdminVideoTimestampCommentSerializer,
    AdminVideoTimestampCommentStatusSerializer,
    AdminVisitorMessageSerializer,
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
