"""Tests for approved_comments_count on the public video detail endpoint."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from gallery.models import Album, VideoClip, VideoTimestampComment

_PUBLIC_VIDEO_DETAIL_URL = '/api/public/videos/{}/'
_PUBLIC_VIDEO_LIST_URL = '/api/public/videos/'


def _make_ready_video(**kwargs):
    defaults = {
        'cloudflare_uid': f'uid-cc-{VideoClip.objects.count()}-{id(kwargs)}',
        'status': VideoClip.STATUS_READY,
        'is_public': True,
        'title_bs': 'Test Video BS',
        'title_en': 'Test Video EN',
    }
    defaults.update(kwargs)
    return VideoClip.objects.create(**defaults)


def _make_comment(video, comment_status, **kwargs):
    defaults = {
        'author_name': 'Tester',
        'author_email': 'tester@example.com',
        'text': 'Test comment',
        'timestamp_seconds': 10,
        'status': comment_status,
    }
    defaults.update(kwargs)
    return VideoTimestampComment.objects.create(video=video, **defaults)


class PublicVideoDetailApprovedCommentCountTests(TestCase):
    """approved_comments_count field on GET /api/public/videos/<pk>/."""

    def setUp(self):
        self.client = APIClient()
        self.video = _make_ready_video(cloudflare_uid='uid-cc-main')
        self.other_video = _make_ready_video(cloudflare_uid='uid-cc-other')

    def test_detail_includes_approved_comments_count_field(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('approved_comments_count', resp.data)

    def test_count_is_zero_when_no_comments(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 0)

    def test_count_reflects_approved_comments(self):
        _make_comment(self.video, VideoTimestampComment.STATUS_APPROVED)
        _make_comment(self.video, VideoTimestampComment.STATUS_APPROVED)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 2)

    def test_pending_comments_not_counted(self):
        _make_comment(self.video, VideoTimestampComment.STATUS_PENDING)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 0)

    def test_rejected_comments_not_counted(self):
        _make_comment(self.video, VideoTimestampComment.STATUS_REJECTED)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 0)

    def test_only_approved_counted_in_mixed_set(self):
        _make_comment(self.video, VideoTimestampComment.STATUS_APPROVED)
        _make_comment(self.video, VideoTimestampComment.STATUS_PENDING)
        _make_comment(self.video, VideoTimestampComment.STATUS_REJECTED)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 1)

    def test_comments_from_other_video_not_counted(self):
        _make_comment(self.other_video, VideoTimestampComment.STATUS_APPROVED)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['approved_comments_count'], 0)

    def test_list_card_does_not_include_approved_comments_count(self):
        _make_ready_video(cloudflare_uid='uid-cc-list-check')
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = (
            resp.data['results']
            if isinstance(resp.data, dict) and 'results' in resp.data
            else resp.data
        )
        if results:
            self.assertNotIn('approved_comments_count', results[0])
