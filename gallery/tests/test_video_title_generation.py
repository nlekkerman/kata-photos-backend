"""
Focused tests for AI-assisted Bosnian video title generation.

Tests cover:
  - generate_video_title_bs_from_description (unit, fully mocked)
  - resolve_video_titles (unit, fully mocked OpenAI)

Run only these tests:
    python manage.py test gallery.tests.test_video_title_generation

Full backend test suite is intentionally NOT run here.

Patch targets:
  "openai.OpenAI" — patched at the module attribute level (same pattern as
  test_openai_auto_translation.py) because the import is deferred inside the
  service function body.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

_OPENAI_PATCH = "openai.OpenAI"


def _make_openai_response(payload: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Unit tests — generate_video_title_bs_from_description
# ---------------------------------------------------------------------------

class GenerateTitleBsTests(TestCase):
    """Tests for gallery.services.video_titles.generate_video_title_bs_from_description."""

    def _call_with_openai(self, description, ai_payload):
        from gallery.services.video_titles import generate_video_title_bs_from_description

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(ai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                return generate_video_title_bs_from_description(description)

    def _call_no_key(self, description):
        from gallery.services.video_titles import generate_video_title_bs_from_description

        with override_settings(OPENAI_API_KEY=""):
            return generate_video_title_bs_from_description(description)

    # -- Happy path ----------------------------------------------------------

    def test_generates_short_bosnian_title(self):
        result = self._call_with_openai(
            "Srna prelazi šumski put kod Bihaća.",
            {"title_bs": "Srna kraj Bihaća"},
        )
        self.assertEqual(result, "Srna kraj Bihaća")

    def test_preserves_animal_and_location_terms(self):
        result = self._call_with_openai(
            "Mladi medvjed se kreće grebenom Plješevice.",
            {"title_bs": "Medvjed na Plješevici"},
        )
        self.assertIn("Medvjed", result)
        self.assertIn("Plješevici", result)

    def test_preserves_bosnian_characters(self):
        result = self._call_with_openai(
            "Lisica prolazi pored kamere tokom noći.",
            {"title_bs": "Noćna lisica"},
        )
        self.assertIn("ć", result)

    # -- Failure / fallback cases --------------------------------------------

    def test_returns_none_when_api_key_missing(self):
        result = self._call_no_key("Srna prelazi šumski put.")
        self.assertIsNone(result)

    def test_returns_none_when_description_blank(self):
        from gallery.services.video_titles import generate_video_title_bs_from_description

        with override_settings(OPENAI_API_KEY="test-key"):
            self.assertIsNone(generate_video_title_bs_from_description(""))
            self.assertIsNone(generate_video_title_bs_from_description("   "))
            self.assertIsNone(generate_video_title_bs_from_description(None))

    def test_returns_none_on_invalid_json_response(self):
        from gallery.services.video_titles import generate_video_title_bs_from_description

        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = "not valid json {{{"
        choice = MagicMock()
        choice.message = msg
        mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                result = generate_video_title_bs_from_description("Medvjed na gori.")
        self.assertIsNone(result)

    def test_returns_none_on_empty_title_in_response(self):
        result = self._call_with_openai(
            "Medvjed na gori.",
            {"title_bs": ""},
        )
        self.assertIsNone(result)

    def test_long_ai_title_is_capped(self):
        """AI title longer than _TITLE_MAX_LEN is hard-capped before returning."""
        from gallery.services.video_titles import _TITLE_MAX_LEN, generate_video_title_bs_from_description

        long_title = "Č" * (_TITLE_MAX_LEN + 50)  # deliberately over limit, Bosnian char
        result = self._call_with_openai("Srna u šumi.", {"title_bs": long_title})
        self.assertIsNotNone(result)
        self.assertEqual(len(result), _TITLE_MAX_LEN)
        # Confirm Bosnian characters are not corrupted (Python slicing is Unicode-safe)
        self.assertTrue(all(c == "Č" for c in result))

    def test_returns_none_on_openai_exception(self):
        from gallery.services.video_titles import generate_video_title_bs_from_description

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                result = generate_video_title_bs_from_description("Lisica noću.")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Unit tests — resolve_video_titles
# ---------------------------------------------------------------------------

class ResolveVideoTitlesTests(TestCase):
    """Tests for gallery.services.video_titles.resolve_video_titles."""

    def _call(self, *, title_bs, title_en, description_bs,
              original_filename=None, ai_payload=None, now=None, ai_raises=False):
        from gallery.services.video_titles import resolve_video_titles

        mock_client = MagicMock()
        if ai_raises:
            mock_client.chat.completions.create.side_effect = RuntimeError("fail")
        else:
            resp_payload = ai_payload if ai_payload is not None else {}
            mock_client.chat.completions.create.return_value = _make_openai_response(resp_payload)

        with override_settings(OPENAI_API_KEY="test-key" if ai_payload is not None or ai_raises else ""):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                return resolve_video_titles(
                    title_bs=title_bs,
                    title_en=title_en,
                    description_bs=description_bs,
                    original_filename=original_filename,
                    now=now,
                )

    # -- title_bs already provided -------------------------------------------

    def test_provided_title_bs_is_preserved(self):
        bs, en = self._call(
            title_bs="Orao nad planinom",
            title_en="",
            description_bs="Opis orla.",
            # AI should NOT be called; pass payload anyway to avoid patching issues
            ai_payload={"title_bs": "SHOULD NOT BE USED"},
        )
        self.assertEqual(bs, "Orao nad planinom")

    def test_provided_title_en_is_preserved(self):
        bs, en = self._call(
            title_bs="Orao nad planinom",
            title_en="Eagle above the mountain",
            description_bs="",
            ai_payload={},
        )
        self.assertEqual(en, "Eagle above the mountain")

    def test_whitespace_only_title_bs_is_treated_as_blank(self):
        bs, _ = self._call(
            title_bs="   ",
            title_en="",
            description_bs="Srna prelazi šumski put.",
            ai_payload={"title_bs": "Srna u šumi"},
        )
        self.assertEqual(bs, "Srna u šumi")

    # -- title_bs generated from description ---------------------------------

    def test_blank_title_bs_generates_from_description(self):
        bs, _ = self._call(
            title_bs="",
            title_en="",
            description_bs="Srna prelazi šumski put kod Bihaća.",
            ai_payload={"title_bs": "Srna kraj Bihaća"},
        )
        self.assertEqual(bs, "Srna kraj Bihaća")

    def test_none_title_bs_generates_from_description(self):
        bs, _ = self._call(
            title_bs=None,
            title_en=None,
            description_bs="Majka divlja svinja hrani praščiće.",
            ai_payload={"title_bs": "Divlja svinja s mladima"},
        )
        self.assertEqual(bs, "Divlja svinja s mladima")

    # -- title_en generated from title_bs ------------------------------------

    def test_blank_title_en_is_generated_from_final_title_bs(self):
        """When title_en is blank, translate_bs_to_en_fields is used."""
        from gallery.services.video_titles import resolve_video_titles

        # We need to patch both: OpenAI for title_bs generation AND for translation.
        # Simplest: provide title_bs so no generation needed, then mock translation.
        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(
                "gallery.services.video_titles.translate_bs_to_en_fields",
                return_value={"title_bs": "Deer near Bihać"},
            ):
                bs, en = resolve_video_titles(
                    title_bs="Srna kraj Bihaća",
                    title_en="",
                    description_bs="",
                )
        self.assertEqual(en, "Deer near Bihać")

    def test_title_en_fallback_to_title_bs_when_translation_fails(self):
        """When translation returns empty, title_en falls back to title_bs."""
        from gallery.services.video_titles import resolve_video_titles

        with override_settings(OPENAI_API_KEY=""):
            bs, en = resolve_video_titles(
                title_bs="Srna kraj Bihaća",
                title_en="",
                description_bs="",
            )
        # No API key → translate_bs_to_en_fields returns {}
        self.assertEqual(bs, "Srna kraj Bihaća")
        self.assertEqual(en, "Srna kraj Bihaća")

    # -- Local fallbacks when OpenAI fails -----------------------------------

    def test_fallback_to_first_sentence_when_ai_fails(self):
        bs, _ = self._call(
            title_bs="",
            title_en="",
            description_bs="Srna prelazi šumski put. Vidljiva je jasno.",
            ai_raises=True,
        )
        # Should use first sentence as fallback
        self.assertIn("Srna", bs)

    def test_fallback_to_filename_when_description_blank_and_ai_fails(self):
        bs, _ = self._call(
            title_bs="",
            title_en="",
            description_bs="",
            original_filename="medvjed_pljesevica_2024.mp4",
            ai_raises=True,
        )
        self.assertIn("medvjed", bs.lower())

    def test_fallback_to_timestamp_when_no_hints(self):
        fixed_now = datetime(2025, 6, 8, 10, 30, tzinfo=timezone.utc)
        bs, _ = self._call(
            title_bs="",
            title_en="",
            description_bs="",
            original_filename=None,
            ai_raises=True,
            now=fixed_now,
        )
        self.assertEqual(bs, "Video upload 2025-06-08 10:30")

    # -- Cloudflare meta.name: title_bs never blank --------------------------

    def test_cloudflare_meta_name_never_blank(self):
        """resolve_video_titles must never return a blank title_bs."""
        fixed_now = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        bs, _ = self._call(
            title_bs=None,
            title_en=None,
            description_bs=None,
            original_filename=None,
            ai_raises=True,
            now=fixed_now,
        )
        self.assertTrue(bs.strip(), "title_bs must not be blank")


# ---------------------------------------------------------------------------
# Integration tests — serializer + view for blank title_bs
# ---------------------------------------------------------------------------

_FAKE_CF_RESULT = {"uid": "sertitle-uid-001", "upload_url": "https://upload.videodelivery.net/tus/sertitle-uid-001"}
_PUBLIC_UPLOAD_URL = '/api/gallery/videos/direct-upload/'
_ADMIN_UPLOAD_URL = '/api/gallery/admin/videos/direct-upload/'

_RESOLVE_PATH = 'gallery.services.video_titles.resolve_video_titles'


@override_settings(
    CLOUDFLARE_ACCOUNT_ID="test_account",
    CLOUDFLARE_STREAM_API_TOKEN="test_token",
    CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN="customer-test.cloudflarestream.com",
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS=3600,
    CLOUDFLARE_STREAM_WATERMARK_UID="",
)
class DirectUploadBlankTitleSerializerTests(TestCase):
    """Verify serializers now accept blank title_bs and the view reaches resolve_video_titles."""

    def setUp(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIClient
        from gallery.models import Album

        self.client = APIClient()
        self.staff = User.objects.create_user(username='ser_staff', password='pass', is_staff=True)
        self.client.force_authenticate(user=self.staff)

    # -- Serializer accepts blank title_bs -----------------------------------

    def test_public_serializer_accepts_blank_title_bs(self):
        from gallery.serializers import VideoClipDirectUploadRequestSerializer

        ser = VideoClipDirectUploadRequestSerializer(data={
            'title_bs': '',
            'description_bs': 'Srna prelazi šumski put.',
            'max_duration_seconds': 60,
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_admin_serializer_accepts_blank_title_bs(self):
        from gallery.serializers import AdminVideoDirectUploadSerializer

        ser = AdminVideoDirectUploadSerializer(data={
            'title_bs': '',
            'description_bs': 'Medvjed na grebenu.',
            'max_duration_seconds': 60,
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    # -- View reaches resolve_video_titles with blank title_bs ---------------

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_blank_title_bs_triggers_resolve_video_titles(self, _mock_cf):
        """When title_bs is blank, the view calls resolve_video_titles and the result is saved."""
        with patch(_RESOLVE_PATH, return_value=('Srna kraj Bihaća', 'Deer near Bihać')) as mock_resolve:
            resp = self.client.post(
                _PUBLIC_UPLOAD_URL,
                {'title_bs': '', 'description_bs': 'Srna prelazi šumski put kod Bihaća.', 'max_duration_seconds': 60},
                format='json',
            )
        self.assertEqual(resp.status_code, 201)
        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1]
        self.assertEqual(call_kwargs['title_bs'], '')
        self.assertEqual(call_kwargs['description_bs'], 'Srna prelazi šumski put kod Bihaća.')

        from gallery.models import VideoClip
        clip = VideoClip.objects.get()
        self.assertEqual(clip.title_bs, 'Srna kraj Bihaća')
        self.assertEqual(clip.title_en, 'Deer near Bihać')

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_admin_blank_title_bs_triggers_resolve_video_titles(self, _mock_cf):
        """Admin endpoint: blank title_bs calls resolve_video_titles and saves result."""
        from gallery.models import Album
        Album.objects.create(slug='vid-album', title_bs='Video Album', gallery_type=Album.GALLERY_TYPE_VIDEO)

        with patch(_RESOLVE_PATH, return_value=('Medvjed na Plješevici', 'Bear on Plješevica')) as mock_resolve:
            resp = self.client.post(
                _ADMIN_UPLOAD_URL,
                {'title_bs': '', 'description_bs': 'Medvjed se kreće grebenom.', 'max_duration_seconds': 60},
                format='json',
            )
        self.assertEqual(resp.status_code, 201)
        mock_resolve.assert_called_once()

        from gallery.models import VideoClip
        clip = VideoClip.objects.get()
        self.assertEqual(clip.title_bs, 'Medvjed na Plješevici')

    # -- Human-provided title_bs still wins ----------------------------------

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_provided_title_bs_is_not_overwritten(self, _mock_cf):
        """When title_bs is non-blank, resolve_video_titles preserves it."""
        with patch(_RESOLVE_PATH, return_value=('Orao nad planinom', 'Eagle above the mountain')) as mock_resolve:
            resp = self.client.post(
                _PUBLIC_UPLOAD_URL,
                {'title_bs': 'Orao nad planinom', 'description_bs': 'Opis orla.', 'max_duration_seconds': 60},
                format='json',
            )
        self.assertEqual(resp.status_code, 201)
        call_kwargs = mock_resolve.call_args[1]
        self.assertEqual(call_kwargs['title_bs'], 'Orao nad planinom')

        from gallery.models import VideoClip
        clip = VideoClip.objects.get()
        self.assertEqual(clip.title_bs, 'Orao nad planinom')

    # -- Fallback still produces non-blank title if OpenAI returns None ------

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_fallback_produces_non_blank_title_when_ai_fails(self, _mock_cf):
        """resolve_video_titles fallbacks guarantee a non-blank title_bs even when AI returns None."""
        with override_settings(OPENAI_API_KEY=""):
            resp = self.client.post(
                _PUBLIC_UPLOAD_URL,
                {'title_bs': '', 'description_bs': 'Srna prelazi šumski put.', 'max_duration_seconds': 60},
                format='json',
            )
        self.assertEqual(resp.status_code, 201)
        from gallery.models import VideoClip
        clip = VideoClip.objects.get()
        self.assertTrue(clip.title_bs.strip(), "title_bs must not be blank even when OpenAI is unavailable")
