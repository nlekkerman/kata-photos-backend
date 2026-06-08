"""
Focused tests for the AdminNotificationCheckpoint model and mark-seen endpoint.

New endpoints covered:
    GET  /api/gallery/admin/notifications/        (checkpoint-based counting)
    POST /api/gallery/admin/notifications/mark-seen/

Run only these tests:
    python manage.py test gallery.tests.test_admin_notification_checkpoint
"""

import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gallery.models import (
    AdminNotificationCheckpoint,
    VideoClip,
    VideoTimestampComment,
    VisitorMessage,
)

COUNTS_URL = reverse('admin-notifications')
MARK_SEEN_URL = reverse('admin-notifications-mark-seen')


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_video():
    return VideoClip.objects.create(
        title_bs='Test video',
        cloudflare_uid=f'uid-{VideoClip.objects.count()}-chk',
    )


def _make_message():
    return VisitorMessage.objects.create(
        sender_name='Sender',
        sender_email='s@example.com',
        subject='Subject',
        message='Body',
    )


def _make_comment(video):
    return VideoTimestampComment.objects.create(
        video=video,
        author_name='Author',
        author_email='a@example.com',
        text='Comment.',
        timestamp_seconds=5,
    )


def _staff(username='staff'):
    return User.objects.create_user(username=username, password='pass', is_staff=True)


def _regular(username='regular'):
    return User.objects.create_user(username=username, password='pass', is_staff=False)


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------

class MarkSeenPermissionTests(TestCase):

    def test_unauthenticated_mark_seen_rejected(self):
        response = self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        self.assertIn(response.status_code, [401, 403])

    def test_non_staff_mark_seen_rejected(self):
        self.client.force_login(_regular())
        response = self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        self.assertIn(response.status_code, [401, 403])

    def test_unauthenticated_counts_rejected(self):
        response = self.client.get(COUNTS_URL)
        self.assertIn(response.status_code, [401, 403])

    def test_non_staff_counts_rejected(self):
        self.client.force_login(_regular())
        response = self.client.get(COUNTS_URL)
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Null-checkpoint counting (first request, no checkpoint exists)
# ---------------------------------------------------------------------------

class NullCheckpointCountingTests(TestCase):

    def setUp(self):
        self.staff = _staff()
        self.client.force_login(self.staff)

    def test_first_request_returns_all_existing_messages(self):
        _make_message()
        _make_message()
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 2)

    def test_first_request_returns_all_existing_comments(self):
        video = _make_video()
        _make_comment(video)
        _make_comment(video)
        _make_comment(video)
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['pending_comments_count'], 3)

    def test_first_request_zero_items(self):
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 0)
        self.assertEqual(data['pending_comments_count'], 0)
        self.assertFalse(data['has_notifications'])

    def test_first_request_does_not_create_checkpoint(self):
        self.client.get(COUNTS_URL)
        self.assertFalse(
            AdminNotificationCheckpoint.objects.filter(staff_user=self.staff).exists()
        )


# ---------------------------------------------------------------------------
# Mark-seen: basic behavior
# ---------------------------------------------------------------------------

class MarkSeenBasicTests(TestCase):

    def setUp(self):
        self.staff = _staff()
        self.client.force_login(self.staff)
        self.video = _make_video()

    def test_mark_seen_messages_creates_checkpoint(self):
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        self.assertTrue(
            AdminNotificationCheckpoint.objects.filter(staff_user=self.staff).exists()
        )

    def test_mark_seen_messages_resets_message_count(self):
        _make_message()
        _make_message()
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 0)

    def test_mark_seen_messages_does_not_reset_comment_count(self):
        _make_message()
        _make_comment(self.video)
        _make_comment(self.video)
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 0)
        self.assertEqual(data['pending_comments_count'], 2)

    def test_mark_seen_comments_resets_comment_count(self):
        _make_comment(self.video)
        _make_comment(self.video)
        self.client.post(
            MARK_SEEN_URL, {'section': 'comments'}, content_type='application/json'
        )
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['pending_comments_count'], 0)

    def test_mark_seen_comments_does_not_reset_message_count(self):
        _make_message()
        _make_comment(self.video)
        self.client.post(
            MARK_SEEN_URL, {'section': 'comments'}, content_type='application/json'
        )
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 1)
        self.assertEqual(data['pending_comments_count'], 0)

    def test_mark_seen_all_resets_both_counts(self):
        _make_message()
        _make_comment(self.video)
        self.client.post(
            MARK_SEEN_URL, {'section': 'all'}, content_type='application/json'
        )
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 0)
        self.assertEqual(data['pending_comments_count'], 0)
        self.assertFalse(data['has_notifications'])

    def test_mark_seen_response_shape(self):
        response = self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['section'], 'messages')
        self.assertIn('new_messages_count', data)
        self.assertIn('pending_comments_count', data)
        self.assertIn('total_count', data)
        self.assertIn('has_notifications', data)

    def test_mark_seen_invalid_section_rejected(self):
        response = self.client.post(
            MARK_SEEN_URL, {'section': 'invalid'}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_mark_seen_missing_section_rejected(self):
        response = self.client.post(
            MARK_SEEN_URL, {}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# New items after mark-seen are counted again
# ---------------------------------------------------------------------------

class NewItemsAfterSeenTests(TestCase):

    def setUp(self):
        self.staff = _staff()
        self.client.force_login(self.staff)
        self.video = _make_video()

    def test_new_message_after_mark_seen_is_counted(self):
        # Seen first, then new message arrives
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        # Push seen_at into the past to simulate time passing
        cp = AdminNotificationCheckpoint.objects.get(staff_user=self.staff)
        cp.messages_seen_at = timezone.now() - datetime.timedelta(seconds=5)
        cp.save()

        _make_message()
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['new_messages_count'], 1)

    def test_new_comment_after_mark_seen_is_counted(self):
        self.client.post(
            MARK_SEEN_URL, {'section': 'comments'}, content_type='application/json'
        )
        cp = AdminNotificationCheckpoint.objects.get(staff_user=self.staff)
        cp.comments_seen_at = timezone.now() - datetime.timedelta(seconds=5)
        cp.save()

        _make_comment(self.video)
        data = self.client.get(COUNTS_URL).json()
        self.assertEqual(data['pending_comments_count'], 1)


# ---------------------------------------------------------------------------
# Per-staff checkpoint isolation
# ---------------------------------------------------------------------------

class PerStaffCheckpointTests(TestCase):

    def test_two_staff_users_have_independent_checkpoints(self):
        staff_a = _staff('staff_a')
        staff_b = _staff('staff_b')
        video = _make_video()

        # staff_a marks messages seen
        self.client.force_login(staff_a)
        _make_message()
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )
        data_a = self.client.get(COUNTS_URL).json()
        self.assertEqual(data_a['new_messages_count'], 0)

        # staff_b has not seen anything — still counts the message
        self.client.force_login(staff_b)
        data_b = self.client.get(COUNTS_URL).json()
        self.assertEqual(data_b['new_messages_count'], 1)

    def test_mark_seen_only_updates_own_checkpoint(self):
        staff_a = _staff('staff_a2')
        staff_b = _staff('staff_b2')

        _make_message()

        # staff_a marks seen
        self.client.force_login(staff_a)
        self.client.post(
            MARK_SEEN_URL, {'section': 'messages'}, content_type='application/json'
        )

        # staff_b still sees the message
        self.client.force_login(staff_b)
        data_b = self.client.get(COUNTS_URL).json()
        self.assertEqual(data_b['new_messages_count'], 1)
