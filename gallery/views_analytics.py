"""
Analytics views.

Endpoints:
    POST /api/public/analytics/events/       — anonymous event recording
    GET  /api/gallery/admin/analytics/summary/ — admin KPI dashboard data
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AnalyticsEvent,
    VideoClip,
    VideoTimestampComment,
    VisitorMessage,
)

_PAGE_PATH_MAX = 500
_TOP_PAGES_LIMIT = 10
_TOP_VIDEOS_LIMIT = 10


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

class AnalyticsEventCreateSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=AnalyticsEvent.EVENT_TYPE_CHOICES)
    page_path = serializers.CharField(
        max_length=_PAGE_PATH_MAX,
        required=False,
        allow_blank=True,
        default='',
    )
    video_id = serializers.IntegerField(required=False, allow_null=True)
    album_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_video_id(self, value):
        if value is None:
            return value
        if not VideoClip.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'VideoClip with id={value} does not exist.')
        return value

    def validate_album_id(self, value):
        if value is None:
            return value
        from .models import Album
        if not Album.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'Album with id={value} does not exist.')
        return value


# ---------------------------------------------------------------------------
# Public event endpoint
# ---------------------------------------------------------------------------

class PublicAnalyticsEventView(APIView):
    """
    POST /api/public/analytics/events/

    Records an anonymous analytics event. No auth required.
    No cookies, IP addresses, user-agents, or visitor identities are stored.
    """

    permission_classes = [AllowAny]
    http_method_names = ['post', 'head', 'options']

    def post(self, request):
        serializer = AnalyticsEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        AnalyticsEvent.objects.create(
            event_type=data['event_type'],
            page_path=data.get('page_path', '')[:_PAGE_PATH_MAX],
            video_id=data.get('video_id'),
            album_id=data.get('album_id'),
        )

        return Response({'ok': True}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Admin analytics summary endpoint
# ---------------------------------------------------------------------------

class AdminAnalyticsSummaryView(APIView):
    """
    GET /api/gallery/admin/analytics/summary/

    Returns aggregated KPI data for the admin dashboard.
    Admin-only.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=6)

        # ---- Today totals ---------------------------------------------------
        today_events = AnalyticsEvent.objects.filter(created_at__gte=today_start)
        today_page_views = today_events.filter(
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW
        ).count()
        today_video_plays = today_events.filter(
            event_type=AnalyticsEvent.EVENT_VIDEO_PLAY
        ).count()
        today_comments = VideoTimestampComment.objects.filter(
            created_at__gte=today_start
        ).count()
        today_messages = VisitorMessage.objects.filter(
            created_at__gte=today_start
        ).count()
        pending_comments = VideoTimestampComment.objects.filter(
            status=VideoTimestampComment.STATUS_PENDING
        ).count()
        unread_messages = VisitorMessage.objects.filter(
            status=VisitorMessage.STATUS_NEW
        ).count()

        # ---- Last 7 days rolling ----------------------------------------
        last_7_days = []
        for offset in range(6, -1, -1):
            day_start = today_start - timedelta(days=offset)
            day_end = day_start + timedelta(days=1)
            day_events = AnalyticsEvent.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end
            )
            last_7_days.append({
                'date': day_start.date().isoformat(),
                'page_views': day_events.filter(
                    event_type=AnalyticsEvent.EVENT_PAGE_VIEW
                ).count(),
                'video_plays': day_events.filter(
                    event_type=AnalyticsEvent.EVENT_VIDEO_PLAY
                ).count(),
                'comments_submitted': VideoTimestampComment.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end
                ).count(),
                'visitor_messages': VisitorMessage.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end
                ).count(),
            })

        # ---- Top pages (all time) ----------------------------------------
        top_pages = (
            AnalyticsEvent.objects
            .filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
            .exclude(page_path='')
            .values('page_path')
            .annotate(views=Count('id'))
            .order_by('-views')[:_TOP_PAGES_LIMIT]
        )

        # ---- Top videos (all time) ---------------------------------------
        top_videos_qs = (
            AnalyticsEvent.objects
            .filter(event_type=AnalyticsEvent.EVENT_VIDEO_PLAY, video__isnull=False)
            .values('video_id', 'video__title_bs', 'video__title_en')
            .annotate(plays=Count('id'))
            .order_by('-plays')[:_TOP_VIDEOS_LIMIT]
        )
        top_videos = [
            {
                'video_id': row['video_id'],
                'title_bs': row['video__title_bs'],
                'title_en': row['video__title_en'],
                'plays': row['plays'],
            }
            for row in top_videos_qs
        ]

        return Response({
            'today': {
                'page_views': today_page_views,
                'video_plays': today_video_plays,
                'comments_submitted': today_comments,
                'visitor_messages': today_messages,
                'pending_comments': pending_comments,
                'unread_messages': unread_messages,
            },
            'last_7_days': last_7_days,
            'top_pages': list(top_pages),
            'top_videos': top_videos,
        })
