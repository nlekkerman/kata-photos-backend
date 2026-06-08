"""
Targeted tests for visitor message and video timestamp comment Bosnian translation.

Covers:
  - translate_texts_to_bosnian service function (unit tests, fully mocked)
  - VisitorMessageCreateView: translation wired into perform_create
  - VideoTimestampCommentListCreateView: translation wired into perform_create
  - AdminVisitorMessageSerializer: exposes original + Bosnian fields
  - AdminVideoTimestampCommentSerializer: exposes original + Bosnian fields
  - Public endpoints: do NOT expose translation metadata
  - Failure / missing API key behaviour

Run only these tests:
    python manage.py test gallery.tests.test_visitor_message_translation

Patch target note:
  OpenAI is imported inside the service function body (`from openai import OpenAI`).
  The correct patch target is "openai.OpenAI".
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from gallery.models import Album, VideoClip, VideoTimestampComment, VisitorMessage

User = get_user_model()

_OPENAI_PATCH = "openai.OpenAI"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_response(payload: dict) -> MagicMock:
    """Build a minimal fake openai ChatCompletion response object."""
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_video(album=None, title_bs="Test Video BS", title_en="Test Video EN"):
    return VideoClip.objects.create(
        album=album,
        title_bs=title_bs,
        title_en=title_en,
        cloudflare_uid="uid-test",
        status=VideoClip.STATUS_READY,
        is_public=True,
    )


# ---------------------------------------------------------------------------
# Unit tests — translate_texts_to_bosnian service function
# ---------------------------------------------------------------------------

class TranslateTextsToBosniansUnitTests(TestCase):
    """Unit tests for gallery.services.translation.translate_texts_to_bosnian."""

    def _call(self, fields, openai_payload):
        from gallery.services.translation import translate_texts_to_bosnian

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                return translate_texts_to_bosnian(fields)

    def test_single_field_translated(self):
        result, status, error = self._call(
            {"message": "Beautiful bear!"},
            {"message": "Prelijep medvjed!"},
        )
        self.assertEqual(result, {"message": "Prelijep medvjed!"})
        self.assertEqual(status, "translated")
        self.assertEqual(error, "")

    def test_multiple_fields_translated(self):
        result, status, error = self._call(
            {"subject": "Question about bear video", "message": "Where was this filmed?"},
            {"subject": "Pitanje o videu medvjeda", "message": "Gdje je ovo snimljeno?"},
        )
        self.assertEqual(result["subject"], "Pitanje o videu medvjeda")
        self.assertEqual(result["message"], "Gdje je ovo snimljeno?")
        self.assertEqual(status, "translated")

    def test_whitespace_stripped_from_translation(self):
        result, status, _ = self._call(
            {"message": "Hello"},
            {"message": "  Zdravo  "},
        )
        self.assertEqual(result["message"], "Zdravo")

    def test_no_api_key_returns_skipped(self):
        from gallery.services.translation import translate_texts_to_bosnian

        with override_settings(OPENAI_API_KEY=""):
            result, status, error = translate_texts_to_bosnian({"message": "Hello"})

        self.assertEqual(result, {})
        self.assertEqual(status, "skipped")
        self.assertEqual(error, "")

    def test_empty_fields_returns_skipped(self):
        from gallery.services.translation import translate_texts_to_bosnian

        with override_settings(OPENAI_API_KEY="test-key"):
            result, status, _ = translate_texts_to_bosnian({})

        self.assertEqual(result, {})
        self.assertEqual(status, "skipped")

    def test_openai_exception_returns_failed(self):
        from gallery.services.translation import translate_texts_to_bosnian

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("network error")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                result, status, error = translate_texts_to_bosnian({"message": "Hello"})

        self.assertEqual(result, {})
        self.assertEqual(status, "failed")
        self.assertIn("Translation request failed", error)

    def test_invalid_json_response_returns_failed(self):
        from gallery.services.translation import translate_texts_to_bosnian

        msg = MagicMock()
        msg.content = "not valid json {{{"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                result, status, error = translate_texts_to_bosnian({"message": "Hello"})

        self.assertEqual(result, {})
        self.assertEqual(status, "failed")

    def test_null_value_in_response_excluded(self):
        result, status, _ = self._call(
            {"subject": "Hi", "message": "Hello"},
            {"subject": "Zdravo", "message": None},
        )
        self.assertIn("subject", result)
        self.assertNotIn("message", result)
        self.assertEqual(status, "translated")

    def test_all_null_values_returns_failed(self):
        result, status, _ = self._call(
            {"message": "Hello"},
            {"message": None},
        )
        self.assertEqual(result, {})
        self.assertEqual(status, "failed")


# ---------------------------------------------------------------------------
# VisitorMessage — create view translation tests
# ---------------------------------------------------------------------------

class VisitorMessageTranslationTests(TestCase):
    """
    Integration tests for translation triggered by the public visitor message create endpoint.
    OpenAI is mocked; DB writes are real.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/public/messages/"

    def _post(self, data):
        return self.client.post(self.url, data, format="json")

    def _mock_translation(self, payload):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(payload)
        return patch(_OPENAI_PATCH, return_value=mock_client)

    def test_original_subject_and_message_preserved(self):
        with override_settings(OPENAI_API_KEY="test-key"):
            with self._mock_translation({"subject": "Pitanje", "message": "Poruka na bosanskom"}):
                resp = self._post({
                    "sender_name": "Alice",
                    "sender_email": "alice@example.com",
                    "subject": "Question about the bear video",
                    "message": "Amazing footage, where was this filmed?",
                })
        self.assertEqual(resp.status_code, 201)

        msg = VisitorMessage.objects.get(pk=resp.data["id"])
        # Original text must be exactly as submitted
        self.assertEqual(msg.subject, "Question about the bear video")
        self.assertEqual(msg.message, "Amazing footage, where was this filmed?")

    def test_translation_stored_when_service_succeeds(self):
        translated_subject = "Pitanje o videu medvjeda"
        translated_message = "Nevjerovatan snimak, gdje je ovo snimljeno?"

        with override_settings(OPENAI_API_KEY="test-key"):
            with self._mock_translation({"subject": translated_subject, "message": translated_message}):
                resp = self._post({
                    "sender_name": "Alice",
                    "sender_email": "alice@example.com",
                    "subject": "Question about the bear video",
                    "message": "Amazing footage, where was this filmed?",
                })
        self.assertEqual(resp.status_code, 201)

        msg = VisitorMessage.objects.get(pk=resp.data["id"])
        self.assertEqual(msg.subject_bs, translated_subject)
        self.assertEqual(msg.message_bs, translated_message)
        self.assertEqual(msg.translation_status, "translated")
        self.assertEqual(msg.translation_error, "")

    def test_create_succeeds_when_translation_fails(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("openai down")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                resp = self._post({
                    "sender_name": "Bob",
                    "sender_email": "bob@example.com",
                    "subject": "Test subject",
                    "message": "Test message body.",
                })
        self.assertEqual(resp.status_code, 201)

        msg = VisitorMessage.objects.get(pk=resp.data["id"])
        # Original text preserved
        self.assertEqual(msg.subject, "Test subject")
        self.assertEqual(msg.message, "Test message body.")
        # Translation status recorded as failed
        self.assertEqual(msg.translation_status, "failed")
        # Bosnian fields stay blank
        self.assertEqual(msg.subject_bs, "")
        self.assertEqual(msg.message_bs, "")

    def test_create_succeeds_and_skips_when_no_api_key(self):
        with override_settings(OPENAI_API_KEY=""):
            resp = self._post({
                "sender_name": "Carol",
                "sender_email": "carol@example.com",
                "subject": "Just a question",
                "message": "Some message text.",
            })
        self.assertEqual(resp.status_code, 201)

        msg = VisitorMessage.objects.get(pk=resp.data["id"])
        self.assertEqual(msg.translation_status, "skipped")
        self.assertEqual(msg.subject_bs, "")
        self.assertEqual(msg.message_bs, "")

    def test_public_response_does_not_expose_translation_fields(self):
        with override_settings(OPENAI_API_KEY=""):
            resp = self._post({
                "sender_name": "Dave",
                "sender_email": "dave@example.com",
                "subject": "Hello",
                "message": "A message.",
            })
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("subject_bs", resp.data)
        self.assertNotIn("message_bs", resp.data)
        self.assertNotIn("translation_status", resp.data)
        self.assertNotIn("translation_error", resp.data)


# ---------------------------------------------------------------------------
# VisitorMessage — admin serializer tests
# ---------------------------------------------------------------------------

class AdminVisitorMessageSerializerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin", password="pass", email="admin@example.com"
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_list_exposes_translation_fields(self):
        VisitorMessage.objects.create(
            sender_name="Eve",
            sender_email="eve@example.com",
            subject="Original subject",
            message="Original message",
            subject_bs="Originalna tema",
            message_bs="Originalna poruka",
            translation_status="translated",
            translation_error="",
        )
        resp = self.client.get("/api/gallery/admin/visitor-messages/")
        self.assertEqual(resp.status_code, 200)

        item = resp.data["results"][0]
        self.assertEqual(item["subject"], "Original subject")
        self.assertEqual(item["message"], "Original message")
        self.assertEqual(item["subject_bs"], "Originalna tema")
        self.assertEqual(item["message_bs"], "Originalna poruka")
        self.assertEqual(item["translation_status"], "translated")
        self.assertEqual(item["translation_error"], "")


# ---------------------------------------------------------------------------
# VideoTimestampComment — create view translation tests
# ---------------------------------------------------------------------------

class VideoTimestampCommentTranslationTests(TestCase):
    """
    Integration tests for translation triggered by the public comment create endpoint.
    OpenAI is mocked; DB writes are real.
    """

    def setUp(self):
        self.client = APIClient()
        self.video = _make_video()
        self.url = f"/api/public/videos/{self.video.pk}/comments/"

    def _post(self, data):
        return self.client.post(self.url, data, format="json")

    def _mock_translation(self, payload):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(payload)
        return patch(_OPENAI_PATCH, return_value=mock_client)

    def test_original_text_preserved(self):
        with override_settings(OPENAI_API_KEY="test-key"):
            with self._mock_translation({"text": "Prelijep medvjed!"}):
                resp = self._post({
                    "author_name": "Frank",
                    "author_email": "frank@example.com",
                    "text": "Beautiful bear!",
                    "timestamp_seconds": 42,
                })
        self.assertEqual(resp.status_code, 201)

        comment = VideoTimestampComment.objects.get(pk=resp.data["id"])
        self.assertEqual(comment.text, "Beautiful bear!")

    def test_translation_stored_when_service_succeeds(self):
        translated_text = "Prelijep medvjed!"

        with override_settings(OPENAI_API_KEY="test-key"):
            with self._mock_translation({"text": translated_text}):
                resp = self._post({
                    "author_name": "Grace",
                    "author_email": "grace@example.com",
                    "text": "Beautiful bear!",
                    "timestamp_seconds": 10,
                })
        self.assertEqual(resp.status_code, 201)

        comment = VideoTimestampComment.objects.get(pk=resp.data["id"])
        self.assertEqual(comment.text_bs, translated_text)
        self.assertEqual(comment.translation_status, "translated")
        self.assertEqual(comment.translation_error, "")

    def test_create_succeeds_when_translation_fails(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("openai down")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                resp = self._post({
                    "author_name": "Hank",
                    "author_email": "hank@example.com",
                    "text": "Great footage!",
                    "timestamp_seconds": 5,
                })
        self.assertEqual(resp.status_code, 201)

        comment = VideoTimestampComment.objects.get(pk=resp.data["id"])
        self.assertEqual(comment.text, "Great footage!")
        self.assertEqual(comment.translation_status, "failed")
        self.assertEqual(comment.text_bs, "")

    def test_create_succeeds_and_skips_when_no_api_key(self):
        with override_settings(OPENAI_API_KEY=""):
            resp = self._post({
                "author_name": "Iris",
                "author_email": "iris@example.com",
                "text": "Amazing video.",
                "timestamp_seconds": 20,
            })
        self.assertEqual(resp.status_code, 201)

        comment = VideoTimestampComment.objects.get(pk=resp.data["id"])
        self.assertEqual(comment.translation_status, "skipped")
        self.assertEqual(comment.text_bs, "")

    def test_moderation_status_is_pending(self):
        """Translation should not affect the moderation status of a new comment."""
        with override_settings(OPENAI_API_KEY=""):
            resp = self._post({
                "author_name": "Jake",
                "author_email": "jake@example.com",
                "text": "Cool video.",
                "timestamp_seconds": 30,
            })
        self.assertEqual(resp.status_code, 201)

        comment = VideoTimestampComment.objects.get(pk=resp.data["id"])
        self.assertEqual(comment.status, VideoTimestampComment.STATUS_PENDING)

    def test_public_response_does_not_expose_translation_metadata(self):
        with override_settings(OPENAI_API_KEY=""):
            resp = self._post({
                "author_name": "Kim",
                "author_email": "kim@example.com",
                "text": "Lovely.",
                "timestamp_seconds": 1,
            })
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("text_bs", resp.data)
        self.assertNotIn("translation_status", resp.data)
        self.assertNotIn("translation_error", resp.data)


# ---------------------------------------------------------------------------
# VideoTimestampComment — admin serializer tests
# ---------------------------------------------------------------------------

class AdminVideoTimestampCommentSerializerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin2", password="pass", email="admin2@example.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.video = _make_video()

    def test_admin_list_exposes_translation_fields(self):
        VideoTimestampComment.objects.create(
            video=self.video,
            author_name="Leo",
            author_email="leo@example.com",
            text="Beautiful bear!",
            text_bs="Prelijep medvjed!",
            translation_status="translated",
            translation_error="",
            timestamp_seconds=15,
            status=VideoTimestampComment.STATUS_PENDING,
        )
        resp = self.client.get("/api/gallery/admin/video-timestamp-comments/")
        self.assertEqual(resp.status_code, 200)

        item = resp.data["results"][0]
        self.assertEqual(item["text"], "Beautiful bear!")
        self.assertEqual(item["text_bs"], "Prelijep medvjed!")
        self.assertEqual(item["translation_status"], "translated")
        self.assertEqual(item["translation_error"], "")
