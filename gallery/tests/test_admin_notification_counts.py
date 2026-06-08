"""
Focused tests for the admin notification counts endpoint.

Endpoint: GET /api/gallery/admin/notifications/

Tests cover:
  - staff user receives correct counts
  - unauthenticated request is rejected (403)
  - non-staff authenticated request is rejected (403)
  - zero-count response has correct shape
  - messages with non-new status are not counted
  - comments with non-pending status are not counted

Run only these tests:
    python manage.py test gallery.tests.test_admin_notification_counts
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from gallery.models import VideoClip, VideoTimestampComment, VisitorMessage

URL = reverse('admin-notifications')


def _make_video():
    """Create a minimal VideoClip for use as VideoTimestampComment FK."""
    return VideoClip.objects.create(
        title_bs='Test video',
        cloudflare_uid=f'uid-{VideoClip.objects.count()}-test',
    )


def _make_message(status=VisitorMessage.STATUS_NEW):
    return VisitorMessage.objects.create(
        sender_name='Test Sender',
        sender_email='sender@example.com',
        subject='Test Subject',
        message='Test body.',
        status=status,
    )


def _make_comment(video, status=VideoTimestampComment.STATUS_PENDING):
    return VideoTimestampComment.objects.create(
        video=video,
        author_name='Test Author',
        author_email='author@example.com',
        text='Test comment.',
        timestamp_seconds=10,
        status=status,
    )


class AdminNotificationCountsAuthTests(TestCase):
    """Permission enforcement tests."""

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(URL)
        self.assertIn(response.status_code, [401, 403])

    def test_non_staff_authenticated_request_is_rejected(self):
        user = User.objects.create_user(username='regular', password='pass', is_staff=False)
        self.client.force_login(user)
        response = self.client.get(URL)
        self.assertIn(response.status_code, [401, 403])


class AdminNotificationCountsResponseTests(TestCase):
    """Response shape and counting logic tests."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff', password='pass', is_staff=True
        )
        self.client.force_login(self.staff)

    def test_zero_count_response_shape(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('new_messages_count', data)
        self.assertIn('pending_comments_count', data)
        self.assertIn('total_count', data)
        self.assertIn('has_notifications', data)
        self.assertEqual(data['new_messages_count'], 0)
        self.assertEqual(data['pending_comments_count'], 0)
        self.assertEqual(data['total_count'], 0)
        self.assertFalse(data['has_notifications'])

    def test_counts_new_messages(self):
        _make_message(status=VisitorMessage.STATUS_NEW)
        _make_message(status=VisitorMessage.STATUS_NEW)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['new_messages_count'], 2)
        self.assertEqual(data['pending_comments_count'], 0)
        self.assertEqual(data['total_count'], 2)
        self.assertTrue(data['has_notifications'])

    def test_counts_pending_comments(self):
        video = _make_video()
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['new_messages_count'], 0)
        self.assertEqual(data['pending_comments_count'], 3)
        self.assertEqual(data['total_count'], 3)
        self.assertTrue(data['has_notifications'])

    def test_counts_both_together(self):
        _make_message(status=VisitorMessage.STATUS_NEW)
        video = _make_video()
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['new_messages_count'], 1)
        self.assertEqual(data['pending_comments_count'], 1)
        self.assertEqual(data['total_count'], 2)
        self.assertTrue(data['has_notifications'])

    def test_non_new_messages_are_not_counted(self):
        _make_message(status=VisitorMessage.STATUS_NEW)
        _make_message(status=VisitorMessage.STATUS_READ)
        _make_message(status=VisitorMessage.STATUS_REPLIED)
        _make_message(status=VisitorMessage.STATUS_ARCHIVED)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['new_messages_count'], 1)

    def test_non_pending_comments_are_not_counted(self):
        video = _make_video()
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        _make_comment(video, status=VideoTimestampComment.STATUS_APPROVED)
        _make_comment(video, status=VideoTimestampComment.STATUS_REJECTED)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['pending_comments_count'], 1)

    def test_total_count_matches_sum(self):
        _make_message(status=VisitorMessage.STATUS_NEW)
        _make_message(status=VisitorMessage.STATUS_NEW)
        video = _make_video()
        _make_comment(video, status=VideoTimestampComment.STATUS_PENDING)
        response = self.client.get(URL)
        data = response.json()
        self.assertEqual(data['total_count'], data['new_messages_count'] + data['pending_comments_count'])
