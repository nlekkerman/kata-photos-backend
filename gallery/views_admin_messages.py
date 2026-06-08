"""
Admin-only views for visitor message and video timestamp comment moderation.

Endpoints provided:
    GET  /api/gallery/admin/notifications/
    GET  /api/gallery/admin/visitor-messages/
    GET  /api/gallery/admin/video-timestamp-comments/
    PATCH /api/gallery/admin/video-timestamp-comments/<pk>/
"""

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminNotificationCheckpoint, VideoTimestampComment, VisitorMessage
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
# Notification counts helpers
# ---------------------------------------------------------------------------

def _build_notification_counts(checkpoint):
    """
    Return notification count dict based on checkpoint seen timestamps.
    Counts items created after the seen timestamp; if null, counts all items.
    """
    msg_qs = VisitorMessage.objects.all()
    if checkpoint is not None and checkpoint.messages_seen_at is not None:
        msg_qs = msg_qs.filter(created_at__gt=checkpoint.messages_seen_at)
    new_messages = msg_qs.count()

    cmt_qs = VideoTimestampComment.objects.all()
    if checkpoint is not None and checkpoint.comments_seen_at is not None:
        cmt_qs = cmt_qs.filter(created_at__gt=checkpoint.comments_seen_at)
    pending_comments = cmt_qs.count()

    total = new_messages + pending_comments
    return {
        'new_messages_count': new_messages,
        'pending_comments_count': pending_comments,
        'total_count': total,
        'has_notifications': total > 0,
    }


# ---------------------------------------------------------------------------
# Notification counts
# ---------------------------------------------------------------------------

class AdminNotificationCountsView(APIView):
    """
    GET /api/gallery/admin/notifications/

    Returns aggregate counts for admin UI notification badges.
    Staff/admin only. Never exposes message or comment content.

    Counts are based on items created after the staff user's last seen timestamp
    for each section. If no checkpoint exists yet (first request), all existing
    items are counted.

    Response shape:
        {
            "new_messages_count": <int>,
            "pending_comments_count": <int>,
            "total_count": <int>,
            "has_notifications": <bool>
        }
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        checkpoint = AdminNotificationCheckpoint.objects.filter(
            staff_user=request.user
        ).first()
        return Response(_build_notification_counts(checkpoint))


# ---------------------------------------------------------------------------
# Mark notifications seen
# ---------------------------------------------------------------------------

class AdminMarkNotificationsSeenView(APIView):
    """
    POST /api/gallery/admin/notifications/mark-seen/

    Records the current timestamp as the last-seen checkpoint for the given
    section. Subsequent GET /notifications/ calls will only count items created
    after this timestamp.

    Request body:
        { "section": "messages" | "comments" | "all" }

    Response shape (same as GET /notifications/ plus ok/section):
        {
            "ok": true,
            "section": "messages",
            "new_messages_count": 0,
            "pending_comments_count": 7,
            "total_count": 7,
            "has_notifications": true
        }
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    _ALLOWED_SECTIONS = frozenset({'messages', 'comments', 'all'})

    def post(self, request):
        section = request.data.get('section', '')
        if section not in self._ALLOWED_SECTIONS:
            return Response(
                {'error': 'Invalid section. Allowed values: messages, comments, all.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        checkpoint, _ = AdminNotificationCheckpoint.objects.get_or_create(
            staff_user=request.user
        )

        if section in ('messages', 'all'):
            checkpoint.messages_seen_at = now
        if section in ('comments', 'all'):
            checkpoint.comments_seen_at = now
        checkpoint.save()

        counts = _build_notification_counts(checkpoint)
        return Response({
            'ok': True,
            'section': section,
            'new_messages_count': counts['new_messages_count'],
            'pending_comments_count': counts['pending_comments_count'],
            'total_count': counts['total_count'],
            'has_notifications': counts['has_notifications'],
        })
