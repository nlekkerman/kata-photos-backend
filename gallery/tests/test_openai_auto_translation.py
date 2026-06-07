"""
Focused tests for the OpenAI Bosnian → English auto-translation feature.

Covers:
  - gallery.services.translation.translate_bs_to_en_fields (unit tests, fully mocked)
  - gallery.signals  (integration tests against real DB models, OpenAI mocked)

Run only these tests:
    python manage.py test gallery.tests.test_openai_auto_translation

Full backend test suite is intentionally NOT run here.

Patch target note:
  OpenAI is imported inside the service function body (`from openai import OpenAI`).
  The correct patch target is "openai.OpenAI" — patching the attribute on the openai
  module itself, which Python resolves at call time when the local import runs.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from gallery.models import Album, FieldNote, MediaItem, VideoClip

# Patch target: openai.OpenAI is resolved at call time by the local import inside
# the service function. Patching the module attribute intercepts it correctly.
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


# ---------------------------------------------------------------------------
# Unit tests — translation service
# ---------------------------------------------------------------------------

class TranslationServiceUnitTests(TestCase):
    """Tests for gallery.services.translation.translate_bs_to_en_fields."""

    def _call(self, fields, openai_payload):
        from gallery.services.translation import translate_bs_to_en_fields

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                return translate_bs_to_en_fields(fields)

    # -- Happy path ----------------------------------------------------------

    def test_single_field_translated(self):
        result = self._call(
            {"title_bs": "Srna u šumi"},
            {"title_bs": "Roe deer in the forest"},
        )
        self.assertEqual(result, {"title_bs": "Roe deer in the forest"})

    def test_multiple_fields_translated(self):
        result = self._call(
            {"title_bs": "Orao", "description_bs": "Opis orla"},
            {"title_bs": "Eagle", "description_bs": "Description of an eagle"},
        )
        self.assertEqual(result["title_bs"], "Eagle")
        self.assertEqual(result["description_bs"], "Description of an eagle")

    def test_whitespace_stripped_from_translation(self):
        result = self._call(
            {"title_bs": "Vuk"},
            {"title_bs": "  Wolf  "},
        )
        self.assertEqual(result["title_bs"], "Wolf")

    # -- Missing API key -----------------------------------------------------

    def test_no_api_key_returns_empty(self):
        from gallery.services.translation import translate_bs_to_en_fields

        with override_settings(OPENAI_API_KEY=""):
            result = translate_bs_to_en_fields({"title_bs": "Tekst"})
        self.assertEqual(result, {})

    # -- Empty / blank input -------------------------------------------------

    def test_empty_fields_dict_returns_empty(self):
        from gallery.services.translation import translate_bs_to_en_fields

        with override_settings(OPENAI_API_KEY="test-key"):
            result = translate_bs_to_en_fields({})
        self.assertEqual(result, {})

    # -- OpenAI failure scenarios --------------------------------------------

    def test_openai_exception_returns_empty(self):
        from gallery.services.translation import translate_bs_to_en_fields

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("network error")

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                result = translate_bs_to_en_fields({"title_bs": "Tekst"})

        self.assertEqual(result, {})

    def test_invalid_json_response_returns_empty(self):
        from gallery.services.translation import translate_bs_to_en_fields

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
                result = translate_bs_to_en_fields({"title_bs": "Tekst"})

        self.assertEqual(result, {})

    def test_null_value_in_response_excluded(self):
        """OpenAI returns null for a key — that key should be excluded from result."""
        result = self._call(
            {"title_bs": "Tekst", "description_bs": "Opis"},
            {"title_bs": "Text", "description_bs": None},
        )
        self.assertIn("title_bs", result)
        self.assertNotIn("description_bs", result)

    def test_empty_string_value_in_response_excluded(self):
        result = self._call(
            {"title_bs": "Tekst"},
            {"title_bs": ""},
        )
        self.assertEqual(result, {})

    def test_extra_keys_in_response_ignored(self):
        """OpenAI response may include extra keys — only requested keys returned."""
        result = self._call(
            {"title_bs": "Tekst"},
            {"title_bs": "Text", "injected_key": "hacked"},
        )
        self.assertIn("title_bs", result)
        self.assertNotIn("injected_key", result)

    def test_partial_response_returns_valid_keys_only(self):
        """If OpenAI omits some requested keys, only valid ones come back."""
        result = self._call(
            {"title_bs": "Tekst", "description_bs": "Opis"},
            {"title_bs": "Text"},   # description_bs missing
        )
        self.assertEqual(result, {"title_bs": "Text"})


# ---------------------------------------------------------------------------
# Integration tests — signals
#
# All signal test classes use OPENAI_API_KEY="" by default (class-level
# override_settings) so that setUp creates and incidental full saves never
# hit the real OpenAI API.  Individual test methods that want to exercise
# translation re-override to "test-key" and patch openai.OpenAI.
# ---------------------------------------------------------------------------

@override_settings(OPENAI_API_KEY="")
class VideoClipTranslationSignalTests(TestCase):
    """Post-save signal fires translation for VideoClip when English is blank."""

    def setUp(self):
        # API key is "" for this class, so Album create won't attempt translation.
        self.album = Album.objects.create(
            title_bs="Test album",
            slug="test-album-vc",
            gallery_type=Album.GALLERY_TYPE_VIDEO,
        )

    def _create_video(self, title_en="", description_en="", openai_payload=None):
        if openai_payload is None:
            openai_payload = {"title_bs": "Eagle", "description_bs": "Eagle description"}

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                video = VideoClip.objects.create(
                    album=self.album,
                    title_bs="Orao",
                    title_en=title_en,
                    description_bs="Opis orla",
                    description_en=description_en,
                    cloudflare_uid="uid-test-001",
                )
        return video

    def test_english_fields_populated_on_create(self):
        video = self._create_video()
        video.refresh_from_db()
        self.assertEqual(video.title_en, "Eagle")
        self.assertEqual(video.description_en, "Eagle description")

    def test_existing_english_not_overwritten(self):
        """If title_en already has content, it must not be replaced."""
        video = self._create_video(
            title_en="Manually set eagle",
            openai_payload={"description_bs": "Eagle description"},
        )
        video.refresh_from_db()
        self.assertEqual(video.title_en, "Manually set eagle")

    def test_no_api_key_leaves_english_blank(self):
        # OPENAI_API_KEY is already "" from the class decorator.
        video = VideoClip.objects.create(
            album=self.album,
            title_bs="Vuk",
            cloudflare_uid="uid-test-002",
        )
        video.refresh_from_db()
        self.assertEqual(video.title_en, "")

    def test_partial_save_does_not_trigger_translation(self):
        """save(update_fields=...) must NOT instantiate OpenAI client."""
        # Create without translation (API key is "").
        video = VideoClip.objects.create(
            album=self.album,
            title_bs="Srna",
            cloudflare_uid="uid-test-003",
        )
        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH) as MockOpenAI:
                video.status = VideoClip.STATUS_READY
                video.save(update_fields=["status"])
                MockOpenAI.assert_not_called()


@override_settings(OPENAI_API_KEY="")
class AlbumTranslationSignalTests(TestCase):
    """Post-save signal fires translation for Album."""

    def _create_album(self, openai_payload=None):
        if openai_payload is None:
            openai_payload = {
                "title_bs": "Wildlife gallery",
                "description_bs": "A gallery of wild animals",
            }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                album = Album.objects.create(
                    title_bs="Galerija divljači",
                    description_bs="Galerija divljih životinja",
                    slug="galerija-divljaci",
                )
        return album

    def test_english_fields_populated_on_create(self):
        album = self._create_album()
        album.refresh_from_db()
        self.assertEqual(album.title_en, "Wildlife gallery")
        self.assertEqual(album.description_en, "A gallery of wild animals")

    def test_existing_english_not_overwritten_on_update(self):
        album = self._create_album(openai_payload={"title_bs": "Wildlife gallery"})
        album.refresh_from_db()
        existing_title_en = album.title_en

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(
            {"title_bs": "SHOULD NOT REPLACE"}
        )
        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                album.title_bs = "Nova galerija divljači"
                album.save()

        album.refresh_from_db()
        # English was already set — must not be touched.
        self.assertEqual(album.title_en, existing_title_en)


@override_settings(OPENAI_API_KEY="")
class MediaItemTranslationSignalTests(TestCase):
    """Post-save signal fires translation for MediaItem."""

    def setUp(self):
        self.album = Album.objects.create(
            title_bs="Slike",
            slug="slike",
        )

    def test_title_and_alt_text_translated_on_create(self):
        openai_payload = {
            "title_bs": "Brown bear",
            "alt_text_bs": "A brown bear in the river",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                item = MediaItem.objects.create(
                    album=self.album,
                    title_bs="Smeđi medvjed",
                    alt_text_bs="Smeđi medvjed u rijeci",
                )

        item.refresh_from_db()
        self.assertEqual(item.title_en, "Brown bear")
        self.assertEqual(item.alt_text_en, "A brown bear in the river")


@override_settings(OPENAI_API_KEY="")
class FieldNoteTranslationSignalTests(TestCase):
    """Post-save signal fires translation for FieldNote (excerpt only)."""

    def test_excerpt_en_translated_when_blank(self):
        openai_payload = {"excerpt_bs": "A short excerpt about wolves."}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(openai_payload)

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                note = FieldNote.objects.create(
                    slug="vuk-biljeska",
                    title_en="Notes on wolves",
                    body_en="Body text about wolves.",
                    excerpt_bs="Kratki uvod o vukovima.",
                )

        note.refresh_from_db()
        self.assertEqual(note.excerpt_en, "A short excerpt about wolves.")

    def test_excerpt_en_not_overwritten_if_present(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response({})

        with override_settings(OPENAI_API_KEY="test-key"):
            with patch(_OPENAI_PATCH, return_value=mock_client):
                note = FieldNote.objects.create(
                    slug="medvjed-biljeska",
                    title_en="Notes on bears",
                    body_en="Body text about bears.",
                    excerpt_bs="Kratki uvod o medvjedima.",
                    excerpt_en="Already written excerpt.",
                )

        note.refresh_from_db()
        self.assertEqual(note.excerpt_en, "Already written excerpt.")
