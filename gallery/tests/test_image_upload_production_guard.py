"""
Production guard tests for image upload via _save_media_item_with_cloudflare.

Covers four scenarios:
  1. DEBUG=True  + CF credentials missing  → local fallback allowed (no error)
  2. DEBUG=False + CF credentials missing  → upload rejected (HTTP 502, no MediaItem created)
  3. DEBUG=False + CF credentials present  → Cloudflare upload path used (mocked)
  4. DEBUG=True  + CF credentials present  → Cloudflare upload path used (mocked)

Run only these tests:
    python manage.py test gallery.tests.test_image_upload_production_guard

Patch target for Cloudflare upload:
    gallery.views.upload_image
    (imported inside _save_media_item_with_cloudflare via
     `from .services.cloudflare_images import CloudflareUploadError, upload_image`)
"""
import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from gallery.models import Album, MediaItem

_ADMIN_IMAGES_URL = '/api/gallery/admin/images/'

_FAKE_CF_RESULT = {
    "cf_id": "fake-cf-id-001",
    "public_url": "https://imagedelivery.net/fake-account/fake-cf-id-001/public",
    "thumbnail_url": "https://imagedelivery.net/fake-account/fake-cf-id-001/thumbnail",
}


def _make_image_file(name='photo.jpg'):
    """Return a minimal in-memory JPEG as a SimpleUploadedFile."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    Image.new('RGB', (20, 20), color=(10, 20, 30)).save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


class ImageUploadProductionGuardTests(TestCase):
    """
    Tests that _save_media_item_with_cloudflare enforces the production guard:

      DEBUG=False + missing CF token → rejected (no DB row created)
      DEBUG=True  + missing CF token → local fallback allowed
      CF credentials present         → Cloudflare upload path used
    """

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='guard_staff', password='pass', is_staff=True
        )
        self.client.force_authenticate(user=self.staff)
        self.album = Album.objects.create(
            slug='guard-test-album',
            title_bs='Guard Test Album',
            gallery_type=Album.GALLERY_TYPE_IMAGE,
        )

    # ------------------------------------------------------------------
    # Test 1: DEBUG=False + CF credentials missing → upload rejected
    # ------------------------------------------------------------------
    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='',
        CLOUDFLARE_IMAGES_API_TOKEN='',
    )
    def test_production_missing_cf_token_returns_502(self):
        """Without CF credentials in production, upload is rejected with HTTP 502."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='',
        CLOUDFLARE_IMAGES_API_TOKEN='',
    )
    def test_production_rejection_creates_no_media_item(self):
        """Rejected production upload must not persist any MediaItem row."""
        f = _make_image_file()
        self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(MediaItem.objects.count(), 0)

    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='acct-only',
        CLOUDFLARE_IMAGES_API_TOKEN='',
    )
    def test_production_missing_token_only_returns_502(self):
        """Account ID set but API token missing in production → still rejected."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(MediaItem.objects.count(), 0)

    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='',
        CLOUDFLARE_IMAGES_API_TOKEN='',
    )
    def test_production_rejection_error_message(self):
        """Rejection response contains a meaningful error detail."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        detail = str(resp.data.get('detail', ''))
        self.assertIn('Cloudflare Images is not configured', detail)

    # ------------------------------------------------------------------
    # Test 2: DEBUG=True + CF credentials missing → local fallback allowed
    # ------------------------------------------------------------------
    @override_settings(
        DEBUG=True,
        CLOUDFLARE_ACCOUNT_ID='',
        CLOUDFLARE_IMAGES_API_TOKEN='',
        MEDIA_ROOT=None,  # will be set per-test via tempfile if needed
    )
    def test_debug_missing_cf_allows_local_fallback(self):
        """In DEBUG=True, missing CF credentials fall back to local storage."""
        import tempfile

        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            f = _make_image_file()
            resp = self.client.post(
                _ADMIN_IMAGES_URL,
                {'album': self.album.pk, 'original_file': f},
                format='multipart',
            )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item = MediaItem.objects.get()
        self.assertEqual(item.provider, 'local')

    @override_settings(
        DEBUG=True,
        CLOUDFLARE_ACCOUNT_ID='',
        CLOUDFLARE_IMAGES_API_TOKEN='',
    )
    def test_debug_local_fallback_creates_media_item(self):
        """Local fallback in DEBUG mode creates a MediaItem with provider='local'."""
        import tempfile

        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            f = _make_image_file()
            self.client.post(
                _ADMIN_IMAGES_URL,
                {'album': self.album.pk, 'original_file': f},
                format='multipart',
            )
        self.assertEqual(MediaItem.objects.count(), 1)
        self.assertEqual(MediaItem.objects.get().provider, 'local')

    # ------------------------------------------------------------------
    # Test 3: DEBUG=False + CF credentials present → Cloudflare path used
    # ------------------------------------------------------------------
    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='test-account',
        CLOUDFLARE_IMAGES_API_TOKEN='test-token',
    )
    @patch('gallery.services.cloudflare_images.upload_image', return_value=_FAKE_CF_RESULT)
    def test_production_with_cf_creds_uses_cloudflare(self, mock_upload):
        """With CF credentials in production, the upload goes to Cloudflare Images."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_upload.assert_called_once()
        item = MediaItem.objects.get()
        self.assertEqual(item.provider, 'cloudflare_images')
        self.assertEqual(item.provider_public_id, _FAKE_CF_RESULT['cf_id'])
        self.assertEqual(item.public_url, _FAKE_CF_RESULT['public_url'])
        self.assertEqual(item.thumbnail_url, _FAKE_CF_RESULT['thumbnail_url'])
        self.assertFalse(item.original_file)  # file not stored locally for CF items

    @override_settings(
        DEBUG=False,
        CLOUDFLARE_ACCOUNT_ID='test-account',
        CLOUDFLARE_IMAGES_API_TOKEN='test-token',
    )
    @patch('gallery.services.cloudflare_images.upload_image', return_value=_FAKE_CF_RESULT)
    def test_production_cf_success_returns_201(self, mock_upload):
        """Successful Cloudflare upload in production returns HTTP 201."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # Test 4: DEBUG=True + CF credentials present → Cloudflare path used
    # ------------------------------------------------------------------
    @override_settings(
        DEBUG=True,
        CLOUDFLARE_ACCOUNT_ID='test-account',
        CLOUDFLARE_IMAGES_API_TOKEN='test-token',
    )
    @patch('gallery.services.cloudflare_images.upload_image', return_value=_FAKE_CF_RESULT)
    def test_debug_with_cf_creds_uses_cloudflare(self, mock_upload):
        """Even in DEBUG=True, CF credentials present means Cloudflare path is used."""
        f = _make_image_file()
        resp = self.client.post(
            _ADMIN_IMAGES_URL,
            {'album': self.album.pk, 'original_file': f},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_upload.assert_called_once()
        self.assertEqual(MediaItem.objects.get().provider, 'cloudflare_images')
