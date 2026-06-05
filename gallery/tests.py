import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from .models import Album, MediaItem, Tag, VideoClip

ALBUMS_URL = '/api/gallery/albums/'

_TEMP_MEDIA = tempfile.mkdtemp()


def _make_image(name='test.jpg', size=(10, 10)):
    """Return a small in-memory JPEG as a SimpleUploadedFile."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    Image.new('RGB', size, color=(100, 150, 200)).save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')



class AlbumWriteAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='staff', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='user', password='pass', is_staff=False)

    # --- permission tests ---

    def test_anonymous_cannot_create_album(self):
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Test'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_staff_cannot_create_album(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Test'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # --- create tests ---

    def test_staff_can_create_album_with_title_bs(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Moj Album'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Album.objects.count(), 1)
        self.assertEqual(Album.objects.first().title_bs, 'Moj Album')

    def test_staff_can_create_album_without_english_fields(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Bosanski Album'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Album.objects.first().title_en, '')

    def test_slug_auto_generates_from_title_bs(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Lijepi Album'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['slug'], 'lijepi-album')

    def test_duplicate_slug_returns_validation_error(self):
        Album.objects.create(slug='duplikat', title_bs='Existing')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(ALBUMS_URL, {'title_bs': 'Novi', 'slug': 'duplikat'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('slug', resp.data)

    def test_published_album_without_title_bs_rejected(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(ALBUMS_URL, {'title_bs': '', 'is_published': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- public read test ---

    def test_public_list_returns_only_published(self):
        Album.objects.create(slug='objavljen', title_bs='Objavljen', is_published=True)
        Album.objects.create(slug='nacrt', title_bs='Nacrt', is_published=False)
        resp = self.client.get(ALBUMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('objavljen', slugs)
        self.assertNotIn('nacrt', slugs)


@override_settings(MEDIA_ROOT=_TEMP_MEDIA)
class MediaUploadAPITests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='mstaff', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='muser', password='pass', is_staff=False)
        self.album = Album.objects.create(slug='test-album', title_bs='Test Album', is_published=True)
        self.media_url = f'/api/gallery/albums/{self.album.slug}/media/'

    # --- permission tests ---

    def test_anonymous_cannot_upload_media(self):
        resp = self.client.post(self.media_url, {'original_file': _make_image()}, format='multipart')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_staff_cannot_upload_media(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.media_url, {'original_file': _make_image()}, format='multipart')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # --- create tests ---

    def test_staff_can_upload_image_to_album(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.media_url, {'original_file': _make_image()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MediaItem.objects.count(), 1)

    def test_uploaded_media_attached_to_album(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.media_url, {'original_file': _make_image()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item = MediaItem.objects.get(pk=resp.data['id'])
        self.assertEqual(item.album, self.album)

    def test_uploaded_media_defaults_to_unpublished(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.media_url, {'original_file': _make_image()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item = MediaItem.objects.get(pk=resp.data['id'])
        self.assertFalse(item.is_published)

    def test_width_height_file_size_populated(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            self.media_url, {'original_file': _make_image(size=(20, 15))}, format='multipart'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item = MediaItem.objects.get(pk=resp.data['id'])
        self.assertEqual(item.width, 20)
        self.assertEqual(item.height, 15)
        self.assertIsNotNone(item.file_size)
        self.assertGreater(item.file_size, 0)

    def test_published_without_alt_text_bs_rejected(self):
        self.client.force_authenticate(user=self.staff)
        data = {'original_file': _make_image(), 'is_published': True}
        resp = self.client.post(self.media_url, data, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('alt_text_bs', resp.data)

    # --- public read tests ---

    def test_public_list_excludes_unpublished_media(self):
        MediaItem.objects.create(album=self.album, is_published=False, title_bs='Hidden')
        resp = self.client.get(self.media_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_public_list_includes_published_media(self):
        MediaItem.objects.create(album=self.album, is_published=True, title_bs='Visible')
        resp = self.client.get(self.media_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    # --- patch / delete tests ---

    def test_staff_can_patch_media_metadata(self):
        item = MediaItem.objects.create(album=self.album, is_published=False, title_bs='Original')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            f'/api/gallery/media/{item.pk}/', {'title_bs': 'Updated'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        self.assertEqual(item.title_bs, 'Updated')

    def test_staff_can_delete_media(self):
        item = MediaItem.objects.create(album=self.album, is_published=False, title_bs='To Delete')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'/api/gallery/media/{item.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MediaItem.objects.filter(pk=item.pk).exists())


class AlbumCoverAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='covstaff', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='covuser', password='pass', is_staff=False)
        self.album = Album.objects.create(slug='cover-album', title_bs='Cover Album', is_published=True)
        self.other_album = Album.objects.create(slug='other-album', title_bs='Other Album', is_published=True)
        self.media = MediaItem.objects.create(
            album=self.album, is_published=True, media_type='image', title_bs='Cover Image',
        )
        self.other_media = MediaItem.objects.create(
            album=self.other_album, is_published=True, media_type='image', title_bs='Other Image',
        )
        self.unpublished_media = MediaItem.objects.create(
            album=self.album, is_published=False, media_type='image', title_bs='Unpublished',
        )
        self.cover_url = f'/api/gallery/albums/{self.album.slug}/cover/'

    def test_anonymous_cannot_set_cover(self):
        resp = self.client.patch(self.cover_url, {'cover_media_id': self.media.pk}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_staff_cannot_set_cover(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.patch(self.cover_url, {'cover_media_id': self.media.pk}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_staff_can_set_cover_to_published_image(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(self.cover_url, {'cover_media_id': self.media.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.album.refresh_from_db()
        self.assertEqual(self.album.cover_media_id, self.media.pk)

    def test_staff_cannot_set_cover_to_media_from_another_album(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(self.cover_url, {'cover_media_id': self.other_media.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cover_media_id', resp.data)

    def test_staff_cannot_set_cover_to_unpublished_media(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(self.cover_url, {'cover_media_id': self.unpublished_media.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cover_media_id', resp.data)

    def test_staff_can_clear_cover(self):
        self.album.cover_media = self.media
        self.album.save()
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(self.cover_url, {'cover_media_id': None}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.album.refresh_from_db()
        self.assertIsNone(self.album.cover_media)

    def test_public_album_detail_includes_cover_after_set(self):
        self.album.cover_media = self.media
        self.album.save()
        resp = self.client.get(f'/api/gallery/albums/{self.album.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data.get('cover'))
        self.assertEqual(resp.data['cover']['id'], self.media.pk)

    def test_public_album_list_includes_cover_after_set(self):
        self.album.cover_media = self.media
        self.album.save()
        resp = self.client.get('/api/gallery/albums/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        album_data = next(a for a in resp.data if a['slug'] == self.album.slug)
        self.assertIsNotNone(album_data.get('cover'))
        self.assertEqual(album_data['cover']['id'], self.media.pk)


@override_settings(MEDIA_ROOT=_TEMP_MEDIA)
class UploadSafetyTests(TestCase):
    """Phase 6: backend upload safety hardening."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='safestaff', password='pass', is_staff=True)
        self.album = Album.objects.create(slug='safe-album', title_bs='Safe Album', is_published=True)
        self.url = f'/api/gallery/albums/{self.album.slug}/media/'
        self.client.force_authenticate(user=self.staff)

    def _make_image_file(self, name='img.jpg', fmt='JPEG', content_type='image/jpeg'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        Image.new('RGB', (10, 10), color=(200, 100, 50)).save(buf, format=fmt)
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type=content_type)

    def test_valid_jpeg_upload_accepted(self):
        f = self._make_image_file(name='img.jpg', fmt='JPEG', content_type='image/jpeg')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_valid_png_upload_accepted(self):
        f = self._make_image_file(name='img.png', fmt='PNG', content_type='image/png')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_valid_webp_upload_accepted(self):
        try:
            f = self._make_image_file(name='img.webp', fmt='WEBP', content_type='image/webp')
        except (KeyError, IOError, OSError):
            self.skipTest('WEBP not supported by local Pillow build')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_oversized_upload_rejected(self):
        from gallery.serializers import MAX_IMAGE_UPLOAD_SIZE_MB
        # Build a valid JPEG and pad it with null bytes to exceed the size limit.
        # Pillow ignores trailing bytes after the JPEG EOI marker, so the file
        # passes DRF ImageField validation but fails our size check.
        buf = io.BytesIO()
        Image.new('RGB', (10, 10)).save(buf, format='JPEG')
        jpeg_bytes = buf.getvalue()
        target_size = (MAX_IMAGE_UPLOAD_SIZE_MB + 1) * 1024 * 1024
        large_content = jpeg_bytes + b'\x00' * (target_size - len(jpeg_bytes))
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('big.jpg', large_content, content_type='image/jpeg')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('original_file', resp.data)

    def test_unsupported_content_type_rejected(self):
        # GIF is a real image Pillow accepts, but is not in our allowed set.
        # Django's ImageField normalises content_type to the Pillow-detected
        # MIME type, so only an actual GIF (not a JPEG mislabelled as GIF)
        # will arrive in validate_original_file with content_type='image/gif'.
        buf = io.BytesIO()
        Image.new('P', (10, 10)).save(buf, format='GIF')
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('img.gif', buf.read(), content_type='image/gif')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('original_file', resp.data)

    def test_missing_content_type_rejected(self):
        # A file with an unknown extension and no recognized MIME type is
        # rejected by DRF's ImageField (disallowed extension) before it even
        # reaches our validator.  The response is still a clean 400 with the
        # 'original_file' key — which is all the caller should see.
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        Image.new('RGB', (10, 10)).save(buf, format='JPEG')
        buf.seek(0)
        f = SimpleUploadedFile('img.bin', buf.read(), content_type='application/octet-stream')
        resp = self.client.post(self.url, {'original_file': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('original_file', resp.data)

    def test_published_without_alt_text_bs_rejected(self):
        f = self._make_image_file()
        resp = self.client.post(self.url, {'original_file': f, 'is_published': True}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('alt_text_bs', resp.data)

    def test_public_media_list_still_works(self):
        MediaItem.objects.create(album=self.album, is_published=True, title_bs='Visible')
        MediaItem.objects.create(album=self.album, is_published=False, title_bs='Hidden')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


_VIDEO_DIRECT_UPLOAD_URL = '/api/gallery/videos/direct-upload/'

_FAKE_CF_RESULT = {"uid": "abc123uid", "upload_url": "https://upload.videodelivery.net/tus/abc123"}
_FAKE_WATERMARK_UID = "29b0fa37be907b876f3c5670cfaf8890"


@override_settings(
    CLOUDFLARE_ACCOUNT_ID="test_account",
    CLOUDFLARE_STREAM_API_TOKEN="test_token",
    CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN="customer-test.cloudflarestream.com",
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS=3600,
    CLOUDFLARE_STREAM_WATERMARK_UID=_FAKE_WATERMARK_UID,
)
class VideoClipDirectUploadWatermarkTests(TestCase):
    """Phase watermark: verify watermark UID is forwarded to Cloudflare on every direct upload."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='wstaff', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='wuser', password='pass', is_staff=False)
        self.album = Album.objects.create(slug='wm-album', title_bs='Watermark Album')

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_watermark_uid_forwarded_to_cloudflare(self, mock_upload):
        """Watermark UID from settings is passed to create_direct_upload."""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'Test Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        _, kwargs = mock_upload.call_args
        self.assertEqual(kwargs['watermark_uid'], _FAKE_WATERMARK_UID)

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_direct_upload_creates_videoclip_record(self, mock_upload):
        """A successful direct-upload request creates one VideoClip in uploading state."""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'Test Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VideoClip.objects.count(), 1)
        clip = VideoClip.objects.get()
        self.assertEqual(clip.cloudflare_uid, 'abc123uid')
        self.assertEqual(clip.status, VideoClip.STATUS_UPLOADING)
        self.assertTrue(clip.is_public)

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_response_includes_upload_url(self, mock_upload):
        """Response contains upload_url for the client to push the video file."""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'Test Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['upload_url'], _FAKE_CF_RESULT['upload_url'])

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_anonymous_cannot_request_upload(self, mock_upload):
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'Test Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        mock_upload.assert_not_called()

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_non_staff_cannot_request_upload(self, mock_upload):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'Test Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        mock_upload.assert_not_called()

    def test_cloudflare_rejection_surfaces_as_502(self):
        """If Cloudflare rejects the watermark UID, the view returns HTTP 502."""
        from gallery.services.cloudflare_stream import CloudflareStreamError
        with patch(
            'gallery.services.cloudflare_stream.create_direct_upload',
            side_effect=CloudflareStreamError('bad watermark uid'),
        ):
            self.client.force_authenticate(user=self.staff)
            resp = self.client.post(
                _VIDEO_DIRECT_UPLOAD_URL,
                {'title_bs': 'Test Video', 'max_duration_seconds': 60},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(VideoClip.objects.count(), 0)


@override_settings(
    CLOUDFLARE_ACCOUNT_ID="test_account",
    CLOUDFLARE_STREAM_API_TOKEN="test_token",
    CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN="customer-test.cloudflarestream.com",
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS=3600,
    CLOUDFLARE_STREAM_WATERMARK_UID="",
)
class VideoClipDirectUploadNoWatermarkTests(TestCase):
    """Verify that an empty watermark UID results in upload without watermark field."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='nowmstaff', password='pass', is_staff=True)

    @patch('gallery.services.cloudflare_stream.create_direct_upload', return_value=_FAKE_CF_RESULT)
    def test_empty_watermark_uid_not_forwarded(self, mock_upload):
        """When CLOUDFLARE_STREAM_WATERMARK_UID is empty, watermark_uid='' is passed (no watermark)."""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _VIDEO_DIRECT_UPLOAD_URL,
            {'title_bs': 'No WM Video', 'max_duration_seconds': 60},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        _, kwargs = mock_upload.call_args
        self.assertEqual(kwargs['watermark_uid'], '')


# ===========================================================================
# Tag tests
# ===========================================================================

_ADMIN_TAGS_URL = '/api/gallery/admin/tags/'
_PUBLIC_ALBUMS_URL = '/api/gallery/albums/'
_PUBLIC_VIDEOS_URL = '/api/gallery/videos/'


class TagModelTests(TestCase):
    """Unit tests for the Tag model."""

    def test_tag_creation_with_name_bs(self):
        tag = Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.assertEqual(str(tag), 'Ptice')
        self.assertEqual(tag.slug, 'ptice')

    def test_tag_slug_auto_generated_on_save(self):
        tag = Tag(name_bs='Divlje svinje')
        tag.save()
        self.assertEqual(tag.slug, 'divlje-svinje')

    def test_tag_slug_uniqueness_enforced(self):
        from django.db import IntegrityError
        Tag.objects.create(name_bs='Ptice', slug='ptice')
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name_bs='Ptice duplikat', slug='ptice')

    def test_tag_name_en_is_optional(self):
        tag = Tag.objects.create(name_bs='Medvjedi', slug='medvjedi')
        self.assertEqual(tag.name_en, '')


@override_settings(
    CLOUDFLARE_ACCOUNT_ID="",
    CLOUDFLARE_STREAM_API_TOKEN="",
    CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS=3600,
    CLOUDFLARE_STREAM_WATERMARK_UID="",
)
class TagAdminAPITests(TestCase):
    """Admin API: create, list, update, delete tags."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='tagstaff', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='taguser', password='pass', is_staff=False)

    def test_staff_can_create_tag(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(_ADMIN_TAGS_URL, {'name_bs': 'Ptice'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.count(), 1)
        tag = Tag.objects.get()
        self.assertEqual(tag.name_bs, 'Ptice')
        self.assertEqual(tag.slug, 'ptice')

    def test_staff_can_list_tags(self):
        Tag.objects.create(name_bs='Ptice', slug='ptice')
        Tag.objects.create(name_bs='Medvjedi', slug='medvjedi')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(_ADMIN_TAGS_URL, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_staff_can_update_tag(self):
        tag = Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            f'{_ADMIN_TAGS_URL}{tag.pk}/',
            {'name_en': 'Birds'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tag.refresh_from_db()
        self.assertEqual(tag.name_en, 'Birds')

    def test_staff_can_delete_tag(self):
        tag = Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'{_ADMIN_TAGS_URL}{tag.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Tag.objects.count(), 0)

    def test_non_staff_cannot_create_tag(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(_ADMIN_TAGS_URL, {'name_bs': 'Ptice'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anonymous_cannot_create_tag(self):
        resp = self.client.post(_ADMIN_TAGS_URL, {'name_bs': 'Ptice'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_missing_name_bs_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(_ADMIN_TAGS_URL, {'name_en': 'Birds'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name_bs', resp.data)

    def test_duplicate_slug_returns_400(self):
        Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _ADMIN_TAGS_URL,
            {'name_bs': 'Ptice duplkat', 'slug': 'ptice'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('slug', resp.data)

    def test_very_long_name_bs_rejected(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _ADMIN_TAGS_URL,
            {'name_bs': 'a' * 101},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TagAttachmentTests(TestCase):
    """Tags can be assigned to albums and videos."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='attachstaff', password='pass', is_staff=True)
        self.tag_ptice = Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.tag_ribe = Tag.objects.create(name_bs='Ribe', slug='ribe')

    def test_staff_can_attach_tags_to_album_on_create(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _PUBLIC_ALBUMS_URL,
            {'title_bs': 'Priroda', 'tags': [self.tag_ptice.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        album = Album.objects.get()
        self.assertIn(self.tag_ptice, album.tags.all())

    def test_staff_can_attach_tags_to_album_on_patch(self):
        album = Album.objects.create(slug='priroda', title_bs='Priroda')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            f'{_PUBLIC_ALBUMS_URL}priroda/',
            {'tags': [self.tag_ptice.pk, self.tag_ribe.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        album.refresh_from_db()
        self.assertEqual(album.tags.count(), 2)

    def test_patch_with_empty_tags_clears_tags(self):
        album = Album.objects.create(slug='priroda', title_bs='Priroda')
        album.tags.set([self.tag_ptice])
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            f'{_PUBLIC_ALBUMS_URL}priroda/',
            {'tags': []},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        album.refresh_from_db()
        self.assertEqual(album.tags.count(), 0)

    def test_album_with_no_tags_is_valid(self):
        album = Album.objects.create(slug='bez-tagova', title_bs='Bez tagova')
        self.assertEqual(album.tags.count(), 0)

    def test_deleting_tag_does_not_delete_album(self):
        album = Album.objects.create(slug='priroda', title_bs='Priroda')
        album.tags.add(self.tag_ptice)
        self.tag_ptice.delete()
        self.assertTrue(Album.objects.filter(pk=album.pk).exists())
        self.assertEqual(album.tags.count(), 0)

    def test_videoclip_can_have_tags(self):
        video = VideoClip.objects.create(
            title_bs='Test video', cloudflare_uid='uid-tag-test',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        video.tags.set([self.tag_ptice])
        self.assertIn(self.tag_ptice, video.tags.all())


class TagPublicResponseTests(TestCase):
    """Public responses include tags in the correct format."""

    def setUp(self):
        self.client = APIClient()
        self.tag = Tag.objects.create(name_bs='Ptice', name_en='Birds', slug='ptice')

    def test_public_album_list_includes_tags(self):
        album = Album.objects.create(slug='priroda', title_bs='Priroda', is_published=True)
        album.tags.add(self.tag)
        resp = self.client.get(_PUBLIC_ALBUMS_URL, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        tag_data = resp.data[0]['tags'][0]
        self.assertEqual(tag_data['slug'], 'ptice')
        self.assertEqual(tag_data['name_bs'], 'Ptice')
        self.assertEqual(tag_data['name_en'], 'Birds')

    def test_public_album_with_no_tags_returns_empty_list(self):
        Album.objects.create(slug='priroda', title_bs='Priroda', is_published=True)
        resp = self.client.get(_PUBLIC_ALBUMS_URL, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data[0]['tags'], [])

    def test_public_video_list_includes_tags(self):
        video = VideoClip.objects.create(
            title_bs='Test video', cloudflare_uid='uid-pub-tag',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        video.tags.add(self.tag)
        resp = self.client.get(_PUBLIC_VIDEOS_URL, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        tag_data = resp.data[0]['tags'][0]
        self.assertEqual(tag_data['slug'], 'ptice')


class TagFilterTests(TestCase):
    """Filtering public album/video lists by tag slug."""

    def setUp(self):
        self.client = APIClient()
        self.tag_ptice = Tag.objects.create(name_bs='Ptice', slug='ptice')
        self.tag_ribe = Tag.objects.create(name_bs='Ribe', slug='ribe')

    def test_filter_albums_by_tag_returns_matching_only(self):
        a1 = Album.objects.create(slug='ptice-album', title_bs='Ptice album', is_published=True)
        a1.tags.add(self.tag_ptice)
        a2 = Album.objects.create(slug='ribe-album', title_bs='Ribe album', is_published=True)
        a2.tags.add(self.tag_ribe)
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?tag=ptice', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['slug'], 'ptice-album')

    def test_filter_albums_by_unknown_tag_returns_empty(self):
        Album.objects.create(slug='ptice-album', title_bs='Ptice album', is_published=True)
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?tag=nepostoji', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_search_albums_by_title_bs(self):
        a1 = Album.objects.create(slug='priroda', title_bs='Priroda bosanska', is_published=True)
        Album.objects.create(slug='grad', title_bs='Gradska arhitektura', is_published=True)
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=priroda', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['slug'], 'priroda')

    def test_search_albums_by_tag_name(self):
        a1 = Album.objects.create(slug='ptice-album', title_bs='Wildlife', is_published=True)
        a1.tags.add(self.tag_ptice)
        Album.objects.create(slug='grad', title_bs='Grad', is_published=True)
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=Ptice', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_filter_videos_by_tag(self):
        v1 = VideoClip.objects.create(
            title_bs='Ptice video', cloudflare_uid='uid-ptice',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        v1.tags.add(self.tag_ptice)
        v2 = VideoClip.objects.create(
            title_bs='Ribe video', cloudflare_uid='uid-ribe',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        v2.tags.add(self.tag_ribe)
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?tag=ptice', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['cloudflare_uid'], 'uid-ptice')

    def test_search_videos_by_title(self):
        VideoClip.objects.create(
            title_bs='Orlovi u letu', cloudflare_uid='uid-orlovi',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        VideoClip.objects.create(
            title_bs='Riba na vodi', cloudflare_uid='uid-riba',
            status=VideoClip.STATUS_READY, is_public=True,
        )
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=orlovi', format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


class SeedWildlifeTagsCommandTests(TestCase):
    """Tests for the seed_pljesevica_wildlife_tags management command."""

    # Total number of entries in SEED_TAGS in the management command.
    TOTAL_SEED_COUNT = 84

    def _run_command(self, dry_run=False):
        out = io.StringIO()
        call_command('seed_pljesevica_wildlife_tags', stdout=out, dry_run=dry_run)
        return out.getvalue()

    def test_command_creates_all_seed_tags(self):
        self._run_command()
        self.assertEqual(Tag.objects.count(), self.TOTAL_SEED_COUNT)

    def test_command_output_reports_correct_created_count(self):
        output = self._run_command()
        self.assertIn(f'Created {self.TOTAL_SEED_COUNT}', output)
        self.assertIn('skipped 0', output)

    def test_command_idempotent_on_rerun(self):
        self._run_command()
        self._run_command()
        self.assertEqual(Tag.objects.count(), self.TOTAL_SEED_COUNT)

    def test_second_run_reports_all_skipped(self):
        self._run_command()
        output = self._run_command()
        self.assertIn(f'skipped {self.TOTAL_SEED_COUNT}', output)
        self.assertIn('Created 0', output)

    def test_existing_tag_by_slug_is_not_duplicated(self):
        Tag.objects.create(name_bs='Ptice', name_en='Birds', slug='ptice')
        self._run_command()
        self.assertEqual(Tag.objects.filter(slug='ptice').count(), 1)

    def test_existing_edited_name_en_is_not_overwritten(self):
        Tag.objects.create(name_bs='Ptice', name_en='Custom English Name', slug='ptice')
        self._run_command()
        tag = Tag.objects.get(slug='ptice')
        self.assertEqual(tag.name_en, 'Custom English Name')

    def test_dry_run_does_not_create_tags(self):
        self._run_command(dry_run=True)
        self.assertEqual(Tag.objects.count(), 0)

    def test_dry_run_output_reports_would_create(self):
        output = self._run_command(dry_run=True)
        self.assertIn(f'Would create {self.TOTAL_SEED_COUNT}', output)
        self.assertIn('would skip 0', output)


# ===========================================================================
# Public search coverage tests — expanded fields
# ===========================================================================

class AlbumSearchCoverageTests(TestCase):
    """Expanded ?search= coverage for the public album list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.tag_ptice = Tag.objects.create(name_bs='Ptice', name_en='Birds', slug='ptice')
        self.tag_ribe = Tag.objects.create(name_bs='Ribe', name_en='Fish', slug='ribe')

        self.album_bs = Album.objects.create(
            slug='bosanska-suma',
            title_bs='Bosanska šuma',
            title_en='Bosnian Forest',
            description_bs='Opis šumskog staništa',
            description_en='Description of forest habitat',
            is_published=True,
        )
        self.album_bs.tags.add(self.tag_ptice)

        self.album_en = Album.objects.create(
            slug='mountain-wildlife',
            title_bs='Planinska divljač',
            title_en='Mountain Wildlife',
            description_bs='',
            description_en='High altitude species',
            is_published=True,
        )
        self.album_en.tags.add(self.tag_ribe)

        self.album_notag = Album.objects.create(
            slug='bez-tagova',
            title_bs='Bez tagova',
            title_en='No Tags',
            is_published=True,
        )

    def test_search_by_title_bs(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=bosanska')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bosanska-suma', slugs)
        self.assertNotIn('mountain-wildlife', slugs)

    def test_search_by_title_en(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=Mountain+Wildlife')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('mountain-wildlife', slugs)
        self.assertNotIn('bosanska-suma', slugs)

    def test_search_by_description_bs(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=stanista')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # 'stanišTa' contains 'stanista' via icontains but SQLite won't match diacritics case-insensitively
        # use the actual ascii substring present
        resp2 = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=umskog')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp2.data]
        self.assertIn('bosanska-suma', slugs)

    def test_search_by_description_en(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=habitat')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bosanska-suma', slugs)
        self.assertNotIn('mountain-wildlife', slugs)

    def test_search_by_description_en_altitude(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=altitude')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('mountain-wildlife', slugs)

    def test_search_by_tag_name_bs(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=Ptice')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bosanska-suma', slugs)
        self.assertNotIn('mountain-wildlife', slugs)

    def test_search_by_tag_name_en(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=Birds')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bosanska-suma', slugs)

    def test_search_by_tag_slug(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=ribe')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('mountain-wildlife', slugs)
        self.assertNotIn('bosanska-suma', slugs)

    def test_empty_search_returns_all_published(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)

    def test_whitespace_only_search_returns_all_published(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=   ')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)

    def test_unknown_tag_returns_empty(self):
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?tag=nepostoji')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_combined_tag_and_search(self):
        # tag=ptice narrows to bosanska-suma; search=bosanska further confirms it
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?tag=ptice&search=bosanska')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bosanska-suma', slugs)
        self.assertNotIn('mountain-wildlife', slugs)

    def test_combined_tag_and_search_no_cross_match(self):
        # tag=ptice but search matches only mountain-wildlife title → empty
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?tag=ptice&search=altitude')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_no_duplicate_results_when_album_has_multiple_tags(self):
        self.album_bs.tags.add(self.tag_ribe)  # album_bs now has both tags
        resp = self.client.get(f'{_PUBLIC_ALBUMS_URL}?search=bosanska')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in resp.data]
        self.assertEqual(slugs.count('bosanska-suma'), 1)

    def test_album_with_no_tags_not_excluded_from_empty_search(self):
        resp = self.client.get(_PUBLIC_ALBUMS_URL)
        slugs = [a['slug'] for a in resp.data]
        self.assertIn('bez-tagova', slugs)


# ===========================================================================
# Visitor message reply endpoint tests
# ===========================================================================

_VISITOR_MESSAGE_REPLY_URL = '/api/gallery/admin/visitor-messages/{pk}/reply/'


class VisitorMessageReplyViewTests(TestCase):
    """Tests for POST /api/gallery/admin/visitor-messages/<pk>/reply/."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(username='replystaf', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='replyuser', password='pass', is_staff=False)
        from .models import VisitorMessage
        self.message = VisitorMessage.objects.create(
            sender_name='Ana Hodžić',
            sender_email='ana@example.com',
            subject='Pitanje o videu',
            message='Odakle su snimani orlovi?',
            status=VisitorMessage.STATUS_NEW,
        )
        self.url = _VISITOR_MESSAGE_REPLY_URL.format(pk=self.message.pk)
        self.payload = {
            'reply_subject': 'Re: Pitanje o videu',
            'reply_body': 'Hvala na poruci! Snimci su iz Plješevice.',
        }

    def test_anonymous_cannot_reply(self):
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_staff_cannot_reply(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_staff_reply_returns_200(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('replied_at', resp.data)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reply_updates_message_status_to_replied(self):
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, 'replied')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reply_sets_replied_at(self):
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.message.refresh_from_db()
        self.assertIsNotNone(self.message.replied_at)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reply_creates_visitor_message_reply_record(self):
        from .models import VisitorMessageReply
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.assertEqual(VisitorMessageReply.objects.filter(visitor_message=self.message).count(), 1)
        reply = VisitorMessageReply.objects.get(visitor_message=self.message)
        self.assertEqual(reply.reply_subject, self.payload['reply_subject'])
        self.assertEqual(reply.sent_by, self.staff)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reply_sends_email_to_sender(self):
        from django.core import mail
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ana@example.com', mail.outbox[0].to)
        self.assertEqual(mail.outbox[0].subject, self.payload['reply_subject'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reply_email_body_contains_reply_and_original(self):
        from django.core import mail
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        body = mail.outbox[0].body
        self.assertIn(self.payload['reply_body'], body)
        self.assertIn(self.message.message, body)
        self.assertIn(self.message.subject, body)

    def test_missing_reply_subject_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {'reply_body': 'Hvala'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reply_subject', resp.data)

    def test_blank_reply_subject_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {'reply_subject': '', 'reply_body': 'Hvala'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reply_subject', resp.data)

    def test_missing_reply_body_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {'reply_subject': 'Re: Pitanje'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reply_body', resp.data)

    def test_blank_reply_body_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {'reply_subject': 'Re: Pitanje', 'reply_body': ''}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reply_body', resp.data)

    def test_nonexistent_message_returns_404(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            _VISITOR_MESSAGE_REPLY_URL.format(pk=99999),
            self.payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch('django.core.mail.send_mail', side_effect=Exception('SMTP connection refused'))
    def test_email_failure_returns_502(self, mock_mail):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch('django.core.mail.send_mail', side_effect=Exception('SMTP connection refused'))
    def test_email_failure_does_not_update_message_status(self, mock_mail):
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, 'new')
        self.assertIsNone(self.message.replied_at)

    @patch('django.core.mail.send_mail', side_effect=Exception('SMTP connection refused'))
    def test_email_failure_does_not_create_reply_record(self, mock_mail):
        from .models import VisitorMessageReply
        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, self.payload, format='json')
        self.assertEqual(VisitorMessageReply.objects.count(), 0)


class VideoSearchCoverageTests(TestCase):
    """Expanded ?search= coverage for the public video list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.tag_planina = Tag.objects.create(name_bs='Planina', name_en='Mountain', slug='planina')
        self.tag_rijeka = Tag.objects.create(name_bs='Rijeka', name_en='River', slug='rijeka')

        self.album = Album.objects.create(
            slug='wildlife-album',
            title_bs='Divljač albuma',
            title_en='Wildlife Album',
            is_published=True,
        )

        self.video_bs = VideoClip.objects.create(
            title_bs='Orlovi u planini',
            title_en='Eagles in the Mountains',
            description_bs='Snimci orlova iz zraka',
            description_en='Aerial footage of eagles',
            album=self.album,
            cloudflare_uid='uid-orlovi',
            status=VideoClip.STATUS_READY,
            is_public=True,
        )
        self.video_bs.tags.add(self.tag_planina)

        self.video_en = VideoClip.objects.create(
            title_bs='Riječne ribe',
            title_en='River Fish',
            description_bs='',
            description_en='Underwater river footage',
            album=None,
            cloudflare_uid='uid-ribe-video',
            status=VideoClip.STATUS_READY,
            is_public=True,
        )
        self.video_en.tags.add(self.tag_rijeka)

        self.video_notag = VideoClip.objects.create(
            title_bs='Bez tagova video',
            title_en='No Tags Video',
            cloudflare_uid='uid-notag',
            status=VideoClip.STATUS_READY,
            is_public=True,
        )

    def test_search_by_title_bs(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=orlovi')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)
        self.assertNotIn('uid-ribe-video', uids)

    def test_search_by_title_en(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=River+Fish')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-ribe-video', uids)
        self.assertNotIn('uid-orlovi', uids)

    def test_search_by_description_bs(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=zraka')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)

    def test_search_by_description_en(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=Underwater')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-ribe-video', uids)
        self.assertNotIn('uid-orlovi', uids)

    def test_search_by_album_title_bs(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=albuma')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)

    def test_search_by_album_title_en(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=Wildlife+Album')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)

    def test_search_by_tag_name_bs(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=Planina')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)
        self.assertNotIn('uid-ribe-video', uids)

    def test_search_by_tag_name_en(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=River')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-ribe-video', uids)

    def test_search_by_tag_slug(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=rijeka')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-ribe-video', uids)
        self.assertNotIn('uid-orlovi', uids)

    def test_empty_search_returns_all_public_ready(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)

    def test_whitespace_only_search_returns_all_public_ready(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=   ')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)

    def test_unknown_tag_returns_empty(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?tag=nepostoji')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_combined_tag_and_search(self):
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?tag=planina&search=orlovi')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-orlovi', uids)
        self.assertNotIn('uid-ribe-video', uids)

    def test_combined_tag_and_search_no_cross_match(self):
        # tag=planina but search matches only ribe video → empty
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?tag=planina&search=Underwater')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_no_duplicate_results_when_video_has_multiple_tags(self):
        self.video_bs.tags.add(self.tag_rijeka)  # video_bs now has both tags
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=orlovi')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertEqual(uids.count('uid-orlovi'), 1)

    def test_video_with_no_tags_not_excluded_from_empty_search(self):
        resp = self.client.get(_PUBLIC_VIDEOS_URL)
        uids = [v['cloudflare_uid'] for v in resp.data]
        self.assertIn('uid-notag', uids)

    def test_video_without_album_does_not_error_on_album_search(self):
        # video_en has no album; searching by album title should not 500
        resp = self.client.get(f'{_PUBLIC_VIDEOS_URL}?search=Wildlife+Album')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in resp.data]
        # uid-ribe-video has no album, should not appear for album-title match
        self.assertNotIn('uid-ribe-video', uids)


# ===========================================================================
# Phase 1 — Public cursor-paginated video endpoints
# ===========================================================================

_PUBLIC_VIDEO_LIST_URL = '/api/public/videos/'
_PUBLIC_VIDEO_DETAIL_URL = '/api/public/videos/{}/'

_HEAVY_CARD_FIELDS = ['description_bs', 'description_en', 'title_bs', 'title_en',
                      'updated_at', 'is_public', 'status']


def _make_ready_video(**kwargs):
    """Helper: create a public ready VideoClip with minimal required fields."""
    defaults = {
        'cloudflare_uid': f'uid-{VideoClip.objects.count()}-{id(kwargs)}',
        'status': VideoClip.STATUS_READY,
        'is_public': True,
        'title_bs': 'Test Video BS',
        'title_en': 'Test Video EN',
    }
    defaults.update(kwargs)
    return VideoClip.objects.create(**defaults)


class PublicVideoListAPITests(TestCase):
    """Phase 1: GET /api/public/videos/ — cursor-paginated public video list."""

    def setUp(self):
        self.client = APIClient()
        self.album = Album.objects.create(
            slug='test-album', title_bs='Test Album BS', title_en='Test Album EN',
        )
        self.tag = Tag.objects.create(name_bs='Ptice', name_en='Birds', slug='ptice')

    def _get_results(self, resp):
        """Extract result items from either a paginated or plain list response."""
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    # --- access ---

    def test_anonymous_can_list_videos(self):
        _make_ready_video()
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # --- public/private filtering ---

    def test_returns_only_public_ready_videos(self):
        v_public = _make_ready_video(cloudflare_uid='uid-public')
        _make_ready_video(cloudflare_uid='uid-private', is_public=False)
        _make_ready_video(cloudflare_uid='uid-uploading', status=VideoClip.STATUS_UPLOADING)
        _make_ready_video(cloudflare_uid='uid-processing', status=VideoClip.STATUS_PROCESSING)
        _make_ready_video(cloudflare_uid='uid-failed', status=VideoClip.STATUS_FAILED)
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        uids = [v['cloudflare_uid'] for v in results]
        self.assertIn('uid-public', uids)
        self.assertNotIn('uid-private', uids)
        self.assertNotIn('uid-uploading', uids)
        self.assertNotIn('uid-processing', uids)
        self.assertNotIn('uid-failed', uids)

    def test_excludes_private_videos(self):
        _make_ready_video(cloudflare_uid='uid-priv', is_public=False)
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 0)

    def test_excludes_non_ready_statuses(self):
        for s, uid in [
            (VideoClip.STATUS_UPLOADING, 'uid-up'),
            (VideoClip.STATUS_PROCESSING, 'uid-proc'),
            (VideoClip.STATUS_FAILED, 'uid-fail'),
        ]:
            _make_ready_video(cloudflare_uid=uid, status=s)
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 0)

    # --- pagination ---

    def test_response_is_paginated(self):
        for i in range(14):
            _make_ready_video(cloudflare_uid=f'uid-pag-{i}')
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('next', resp.data)

    def test_page_size_respected(self):
        for i in range(15):
            _make_ready_video(cloudflare_uid=f'uid-sz-{i}')
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?page_size=5')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 5)

    def test_page_size_capped_at_max(self):
        for i in range(55):
            _make_ready_video(cloudflare_uid=f'uid-cap-{i}')
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?page_size=100')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertLessEqual(len(results), 50)

    # --- filters ---

    def test_album_filter(self):
        v_in = _make_ready_video(cloudflare_uid='uid-in-album', album=self.album)
        _make_ready_video(cloudflare_uid='uid-no-album')
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?album={self.album.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        uids = [v['cloudflare_uid'] for v in results]
        self.assertIn('uid-in-album', uids)
        self.assertNotIn('uid-no-album', uids)

    def test_tag_filter(self):
        v_tagged = _make_ready_video(cloudflare_uid='uid-tagged')
        v_tagged.tags.add(self.tag)
        _make_ready_video(cloudflare_uid='uid-untagged')
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?tag=ptice')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        uids = [v['cloudflare_uid'] for v in results]
        self.assertIn('uid-tagged', uids)
        self.assertNotIn('uid-untagged', uids)

    def test_search_filter(self):
        _make_ready_video(cloudflare_uid='uid-match', title_bs='Orlovi u planini')
        _make_ready_video(cloudflare_uid='uid-nomatch', title_bs='Ribe u rijeci')
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?search=orlovi')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        uids = [v['cloudflare_uid'] for v in results]
        self.assertIn('uid-match', uids)
        self.assertNotIn('uid-nomatch', uids)

    # --- language ---

    def test_lang_bs_returns_bosnian_title(self):
        _make_ready_video(
            cloudflare_uid='uid-lang',
            title_bs='Bosanski Naslov',
            title_en='English Title',
        )
        resp = self.client.get(f'{_PUBLIC_VIDEO_LIST_URL}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Bosanski Naslov')

    def test_response_does_not_include_raw_title_fields(self):
        _make_ready_video(cloudflare_uid='uid-fields')
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertGreater(len(results), 0)
        item = results[0]
        for field in _HEAVY_CARD_FIELDS:
            self.assertNotIn(field, item)

    def test_response_includes_expected_card_fields(self):
        _make_ready_video(cloudflare_uid='uid-fields2', album=self.album)
        resp = self.client.get(_PUBLIC_VIDEO_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        item = results[0]
        for field in ['id', 'title', 'album_id', 'album_title', 'cloudflare_uid',
                      'cloudflare_thumbnail_url', 'duration_seconds', 'created_at']:
            self.assertIn(field, item)


class PublicVideoDetailAPITests(TestCase):
    """Phase 1: GET /api/public/videos/<pk>/ — single public ready video detail."""

    def setUp(self):
        self.client = APIClient()
        self.album = Album.objects.create(
            slug='detail-album', title_bs='Detail Album BS', title_en='Detail Album EN',
        )
        self.tag = Tag.objects.create(name_bs='Medvjedi', name_en='Bears', slug='medvjedi')
        self.video = _make_ready_video(
            cloudflare_uid='uid-detail',
            title_bs='Naslov na bosanskom',
            title_en='Title in English',
            description_bs='Opis na bosanskom',
            description_en='Description in English',
            album=self.album,
        )
        self.video.tags.add(self.tag)

    # --- access ---

    def test_anonymous_can_retrieve_public_ready_video(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_returns_404_for_private_video(self):
        priv = _make_ready_video(cloudflare_uid='uid-priv-det', is_public=False)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(priv.pk))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_404_for_uploading_video(self):
        v = _make_ready_video(cloudflare_uid='uid-up-det', status=VideoClip.STATUS_UPLOADING)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(v.pk))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_404_for_processing_video(self):
        v = _make_ready_video(cloudflare_uid='uid-proc-det', status=VideoClip.STATUS_PROCESSING)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(v.pk))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_404_for_failed_video(self):
        v = _make_ready_video(cloudflare_uid='uid-fail-det', status=VideoClip.STATUS_FAILED)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(v.pk))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_404_for_missing_video(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(99999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --- response shape ---

    def test_detail_includes_expected_fields(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ['id', 'title', 'description', 'album_id', 'album_title',
                      'cloudflare_uid', 'cloudflare_thumbnail_url',
                      'cloudflare_playback_url', 'duration_seconds', 'tags', 'created_at']:
            self.assertIn(field, resp.data)

    def test_detail_does_not_include_admin_fields(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ['description_bs', 'description_en', 'title_bs', 'title_en',
                      'updated_at', 'is_public', 'status']:
            self.assertNotIn(field, resp.data)

    def test_detail_lang_bs_returns_bosnian_title(self):
        resp = self.client.get(f'{_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk)}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Naslov na bosanskom')
        self.assertEqual(resp.data['description'], 'Opis na bosanskom')

    def test_detail_album_id_and_title_correct(self):
        resp = self.client.get(f'{_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk)}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['album_id'], self.album.pk)
        self.assertEqual(resp.data['album_title'], 'Detail Album BS')

    def test_detail_tags_returned(self):
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(self.video.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tag_slugs = [t['slug'] for t in resp.data['tags']]
        self.assertIn('medvjedi', tag_slugs)

    def test_detail_video_without_album_returns_none_album_id(self):
        v = _make_ready_video(cloudflare_uid='uid-noalbum-det', album=None)
        resp = self.client.get(_PUBLIC_VIDEO_DETAIL_URL.format(v.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data['album_id'])
        self.assertEqual(resp.data['album_title'], '')


# ===========================================================================
# Public album endpoints (Phase 3A)
# ===========================================================================

_PUBLIC_ALBUM_LIST_URL = '/api/public/albums/'
_PUBLIC_ALBUM_DETAIL_URL = '/api/public/albums/{}/'
_PUBLIC_ALBUM_VIDEOS_URL = '/api/public/albums/{}/videos/'

_ALBUM_ADMIN_FIELDS = [
    'title_bs', 'title_en', 'description_bs', 'description_en',
    'seo_title_bs', 'seo_title_en', 'seo_description_bs', 'seo_description_en',
    'is_published', 'updated_at',
]


def _make_published_album(**kwargs):
    """Helper: create a published Album with minimal required fields."""
    defaults = {
        'slug': f'album-{Album.objects.count()}-{id(kwargs)}',
        'title_bs': 'Test Album BS',
        'title_en': 'Test Album EN',
        'is_published': True,
        'gallery_type': Album.GALLERY_TYPE_VIDEO,
    }
    defaults.update(kwargs)
    return Album.objects.create(**defaults)


class PublicAlbumListAPITests(TestCase):
    """Phase 3A: GET /api/public/albums/ — cursor-paginated public album list."""

    def setUp(self):
        self.client = APIClient()

    def _results(self, resp):
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    # 1. Anonymous user can list public albums.
    def test_anonymous_can_list_albums(self):
        _make_published_album(slug='alb-anon')
        resp = self.client.get(_PUBLIC_ALBUM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # 2. Unpublished albums are excluded.
    def test_unpublished_albums_excluded(self):
        _make_published_album(slug='alb-pub')
        Album.objects.create(slug='alb-draft', title_bs='Draft', is_published=False)
        resp = self.client.get(_PUBLIC_ALBUM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-pub', slugs)
        self.assertNotIn('alb-draft', slugs)

    # 3. Response is paginated.
    def test_response_is_paginated(self):
        for i in range(14):
            _make_published_album(slug=f'alb-pag-{i}')
        resp = self.client.get(_PUBLIC_ALBUM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('next', resp.data)

    # 4. page_size is respected.
    def test_page_size_respected(self):
        for i in range(15):
            _make_published_album(slug=f'alb-sz-{i}')
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?page_size=5')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp)), 5)

    # 5. page_size is capped.
    def test_page_size_capped_at_max(self):
        for i in range(55):
            _make_published_album(slug=f'alb-cap-{i}')
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?page_size=100')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(self._results(resp)), 50)

    # 6. lang=bs returns Bosnian-resolved title/description.
    def test_lang_bs_returns_bosnian_title_and_description(self):
        _make_published_album(
            slug='alb-lang-bs',
            title_bs='Bosanski Naslov',
            title_en='English Title',
            description_bs='Bosanski opis',
            description_en='English description',
        )
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item = next(a for a in self._results(resp) if a['slug'] == 'alb-lang-bs')
        self.assertEqual(item['title'], 'Bosanski Naslov')
        self.assertEqual(item['description'], 'Bosanski opis')

    # 7. Raw bilingual fields are not exposed in list response.
    def test_raw_bilingual_fields_not_in_list(self):
        _make_published_album(slug='alb-fields')
        resp = self.client.get(_PUBLIC_ALBUM_LIST_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._results(resp)
        self.assertGreater(len(results), 0)
        item = results[0]
        for field in _ALBUM_ADMIN_FIELDS:
            self.assertNotIn(field, item)

    # 8. type=video filters video albums.
    def test_type_video_filter(self):
        _make_published_album(slug='alb-vid', gallery_type=Album.GALLERY_TYPE_VIDEO)
        _make_published_album(slug='alb-img', gallery_type=Album.GALLERY_TYPE_IMAGE)
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?type=video')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-vid', slugs)
        self.assertNotIn('alb-img', slugs)

    # 9. type=image filters image albums.
    def test_type_image_filter(self):
        _make_published_album(slug='alb-vid2', gallery_type=Album.GALLERY_TYPE_VIDEO)
        _make_published_album(slug='alb-img2', gallery_type=Album.GALLERY_TYPE_IMAGE)
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?type=image')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-img2', slugs)
        self.assertNotIn('alb-vid2', slugs)

    # 10. tag= filters albums.
    def test_tag_filter(self):
        tag = Tag.objects.create(name_bs='Priroda', name_en='Nature', slug='priroda')
        tagged = _make_published_album(slug='alb-tagged')
        tagged.tags.add(tag)
        _make_published_album(slug='alb-untagged')
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?tag=priroda')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-tagged', slugs)
        self.assertNotIn('alb-untagged', slugs)

    # 11. search= filters albums.
    def test_search_filter(self):
        _make_published_album(slug='alb-match', title_bs='Planinski park')
        _make_published_album(slug='alb-nomatch', title_bs='More i plaža')
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?search=planinski')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-match', slugs)
        self.assertNotIn('alb-nomatch', slugs)

    # 12. populated=true excludes empty published albums.
    def test_populated_excludes_empty_albums(self):
        empty_video_alb = _make_published_album(slug='alb-empty-vid', gallery_type=Album.GALLERY_TYPE_VIDEO)
        populated_vid_alb = _make_published_album(slug='alb-pop-vid', gallery_type=Album.GALLERY_TYPE_VIDEO)
        _make_ready_video(cloudflare_uid='uid-pop-alb', album=populated_vid_alb)
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?populated=true')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-pop-vid', slugs)
        self.assertNotIn('alb-empty-vid', slugs)

    # 13. populated=true&type=video includes only albums with public-ready videos.
    def test_populated_type_video_includes_only_albums_with_ready_videos(self):
        alb_ready = _make_published_album(slug='alb-ready-v', gallery_type=Album.GALLERY_TYPE_VIDEO)
        alb_no_ready = _make_published_album(slug='alb-no-ready-v', gallery_type=Album.GALLERY_TYPE_VIDEO)
        _make_ready_video(cloudflare_uid='uid-ready-v', album=alb_ready)
        # non-ready video on alb_no_ready
        VideoClip.objects.create(
            album=alb_no_ready, title_bs='Not Ready', cloudflare_uid='uid-nr-v',
            status=VideoClip.STATUS_PROCESSING, is_public=True,
        )
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?populated=true&type=video')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-ready-v', slugs)
        self.assertNotIn('alb-no-ready-v', slugs)

    # 14. populated=true&type=image includes only albums with published image media.
    def test_populated_type_image_includes_only_albums_with_published_images(self):
        alb_img_pub = _make_published_album(slug='alb-img-pub', gallery_type=Album.GALLERY_TYPE_IMAGE)
        alb_img_empty = _make_published_album(slug='alb-img-empty', gallery_type=Album.GALLERY_TYPE_IMAGE)
        MediaItem.objects.create(album=alb_img_pub, is_published=True, media_type='image', title_bs='Photo')
        MediaItem.objects.create(album=alb_img_empty, is_published=False, media_type='image', title_bs='Hidden')
        resp = self.client.get(f'{_PUBLIC_ALBUM_LIST_URL}?populated=true&type=image')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [a['slug'] for a in self._results(resp)]
        self.assertIn('alb-img-pub', slugs)
        self.assertNotIn('alb-img-empty', slugs)


class PublicAlbumDetailAPITests(TestCase):
    """Phase 3A: GET /api/public/albums/<slug>/ — single published album detail."""

    def setUp(self):
        self.client = APIClient()
        self.tag = Tag.objects.create(name_bs='Šume', name_en='Forests', slug='sume')
        self.album = _make_published_album(
            slug='alb-detail',
            title_bs='Detalj BS',
            title_en='Detail EN',
            description_bs='Opis BS',
            description_en='Description EN',
            seo_title_bs='SEO BS',
            seo_title_en='SEO EN',
            gallery_type=Album.GALLERY_TYPE_VIDEO,
        )
        self.album.tags.add(self.tag)

    # 1. Anonymous user can retrieve published album.
    def test_anonymous_can_retrieve_published_album(self):
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # 2. Unpublished album returns 404.
    def test_unpublished_album_returns_404(self):
        unpub = Album.objects.create(slug='alb-unpub', title_bs='Unpub', is_published=False)
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(unpub.slug))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 3. Missing album returns 404.
    def test_missing_album_returns_404(self):
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format('does-not-exist'))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 4. lang=bs resolves title/description.
    def test_lang_bs_resolves_title_and_description(self):
        resp = self.client.get(f'{_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug)}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Detalj BS')
        self.assertEqual(resp.data['description'], 'Opis BS')
        self.assertEqual(resp.data['seo_title'], 'SEO BS')

    # 5. Detail includes expected fields.
    def test_detail_includes_expected_fields(self):
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ['id', 'slug', 'title', 'description', 'seo_title', 'seo_description',
                      'gallery_type', 'display_order', 'cover', 'tags', 'created_at']:
            self.assertIn(field, resp.data)

    # 6. Detail does not include nested video/media lists.
    def test_detail_does_not_include_nested_video_or_media_lists(self):
        _make_ready_video(cloudflare_uid='uid-det-vid', album=self.album)
        MediaItem.objects.create(album=self.album, is_published=True, title_bs='Media')
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('videos', resp.data)
        self.assertNotIn('media_items', resp.data)
        self.assertNotIn('media', resp.data)

    def test_detail_does_not_expose_raw_bilingual_fields(self):
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in _ALBUM_ADMIN_FIELDS:
            self.assertNotIn(field, resp.data)

    def test_detail_tags_returned(self):
        resp = self.client.get(_PUBLIC_ALBUM_DETAIL_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tag_slugs = [t['slug'] for t in resp.data['tags']]
        self.assertIn('sume', tag_slugs)


class PublicAlbumVideosAPITests(TestCase):
    """Phase 3A: GET /api/public/albums/<slug>/videos/ — paginated public videos for album."""

    def setUp(self):
        self.client = APIClient()
        self.album = _make_published_album(slug='alb-videos', gallery_type=Album.GALLERY_TYPE_VIDEO)
        self.other_album = _make_published_album(slug='alb-other', gallery_type=Album.GALLERY_TYPE_VIDEO)

    def _results(self, resp):
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    # 1. Anonymous user can list videos for published album.
    def test_anonymous_can_list_album_videos(self):
        _make_ready_video(cloudflare_uid='uid-av-1', album=self.album)
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # 2. Unpublished album returns 404.
    def test_unpublished_album_videos_returns_404(self):
        unpub = Album.objects.create(slug='alb-unpub-v', title_bs='Unpub', is_published=False)
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(unpub.slug))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 3. Missing album returns 404.
    def test_missing_album_videos_returns_404(self):
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format('no-such-album'))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 4. Only public ready videos are returned.
    def test_returns_only_public_ready_videos(self):
        v_ok = _make_ready_video(cloudflare_uid='uid-av-ok', album=self.album)
        _make_ready_video(cloudflare_uid='uid-av-priv', album=self.album, is_public=False)
        _make_ready_video(cloudflare_uid='uid-av-proc', album=self.album, status=VideoClip.STATUS_PROCESSING)
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        uids = [v['cloudflare_uid'] for v in self._results(resp)]
        self.assertIn('uid-av-ok', uids)
        self.assertNotIn('uid-av-priv', uids)
        self.assertNotIn('uid-av-proc', uids)

    # 5. Private and non-ready videos are excluded.
    def test_private_and_non_ready_excluded(self):
        for uid, s, pub in [
            ('uid-av-up', VideoClip.STATUS_UPLOADING, True),
            ('uid-av-fail', VideoClip.STATUS_FAILED, True),
            ('uid-av-np', VideoClip.STATUS_READY, False),
        ]:
            VideoClip.objects.create(
                album=self.album, title_bs='X', cloudflare_uid=uid, status=s, is_public=pub
            )
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp)), 0)

    # 6. Response is paginated.
    def test_response_is_paginated(self):
        for i in range(14):
            _make_ready_video(cloudflare_uid=f'uid-avp-{i}', album=self.album)
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('next', resp.data)

    # 7. page_size is respected / capped.
    def test_page_size_respected_and_capped(self):
        for i in range(55):
            _make_ready_video(cloudflare_uid=f'uid-avc-{i}', album=self.album)
        resp5 = self.client.get(f'{_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug)}?page_size=5')
        self.assertEqual(resp5.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp5)), 5)
        resp_big = self.client.get(f'{_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug)}?page_size=100')
        self.assertEqual(resp_big.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(self._results(resp_big)), 50)

    # 8. Response uses public video card shape and excludes heavy/admin fields.
    def test_response_uses_public_video_card_shape(self):
        _make_ready_video(cloudflare_uid='uid-av-shape', album=self.album)
        resp = self.client.get(_PUBLIC_ALBUM_VIDEOS_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._results(resp)
        self.assertEqual(len(results), 1)
        item = results[0]
        for field in ['id', 'title', 'album_id', 'album_title',
                      'cloudflare_uid', 'cloudflare_thumbnail_url',
                      'duration_seconds', 'created_at']:
            self.assertIn(field, item)
        for field in _HEAVY_CARD_FIELDS:
            self.assertNotIn(field, item)


# ===========================================================================
# Public album media endpoint (Phase 3B)
# ===========================================================================

_PUBLIC_ALBUM_MEDIA_URL = '/api/public/albums/{}/media/'


class PublicAlbumMediaAPITests(TestCase):
    """Phase 3B: GET /api/public/albums/<slug>/media/ — paginated public image media."""

    def setUp(self):
        self.client = APIClient()
        self.album = _make_published_album(slug='alb-media-3b', gallery_type=Album.GALLERY_TYPE_IMAGE)
        self.other_album = _make_published_album(slug='alb-media-other-3b', gallery_type=Album.GALLERY_TYPE_IMAGE)

    def _results(self, resp):
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    def _make_image(self, album=None, is_published=True, media_type='image', **kwargs):
        return MediaItem.objects.create(
            album=album or self.album,
            is_published=is_published,
            media_type=media_type,
            **kwargs,
        )

    # 1. Anonymous user can list media for published image album.
    def test_anonymous_can_list_album_media(self):
        self._make_image(title_bs='Photo')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # 2. Missing album returns 404.
    def test_missing_album_returns_404(self):
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format('no-such-album'))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 3. Unpublished album returns 404.
    def test_unpublished_album_returns_404(self):
        unpub = Album.objects.create(slug='alb-unpub-3b', title_bs='Unpub', is_published=False)
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(unpub.slug))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # 4. Only media from the requested album is returned.
    def test_returns_only_media_from_album(self):
        own = self._make_image(title_bs='Mine')
        self._make_image(album=self.other_album, title_bs='Theirs')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in self._results(resp)]
        self.assertIn(own.pk, ids)
        self.assertEqual(len(ids), 1)

    # 5. Only published media is returned.
    def test_returns_only_published_media(self):
        pub = self._make_image(is_published=True, title_bs='Pub')
        self._make_image(is_published=False, title_bs='Hidden')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in self._results(resp)]
        self.assertIn(pub.pk, ids)
        self.assertEqual(len(ids), 1)

    # 6. Unpublished media is excluded.
    def test_unpublished_media_excluded(self):
        self._make_image(is_published=False, title_bs='Draft')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp)), 0)

    # 7. Non-image media is excluded.
    def test_non_image_media_excluded(self):
        self._make_image(media_type='video', title_bs='Vid')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp)), 0)

    # 8. Response is paginated.
    def test_response_is_paginated(self):
        for i in range(14):
            self._make_image(title_bs=f'Photo {i}', display_order=i)
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('next', resp.data)

    # 9. page_size is respected.
    def test_page_size_respected(self):
        for i in range(20):
            self._make_image(title_bs=f'Photo {i}', display_order=i)
        resp = self.client.get(f'{_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug)}?page_size=5')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._results(resp)), 5)

    # 10. page_size is capped at 50.
    def test_page_size_capped_at_50(self):
        for i in range(55):
            self._make_image(title_bs=f'Photo {i}', display_order=i)
        resp = self.client.get(f'{_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug)}?page_size=100')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(self._results(resp)), 50)

    # 11. lang=bs resolves title/description/alt_text/caption correctly.
    def test_lang_bs_resolves_fields(self):
        MediaItem.objects.create(
            album=self.album,
            is_published=True,
            media_type='image',
            title_bs='Naslov BS',
            title_en='Title EN',
            description_bs='Opis BS',
            alt_text_bs='Alt BS',
            caption_bs='Potpis BS',
        )
        resp = self.client.get(f'{_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug)}?lang=bs')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item = self._results(resp)[0]
        self.assertEqual(item['title'], 'Naslov BS')
        self.assertEqual(item['description'], 'Opis BS')
        self.assertEqual(item['alt_text'], 'Alt BS')
        self.assertEqual(item['caption'], 'Potpis BS')

    # 12. Response does not expose raw bilingual fields.
    def test_no_raw_bilingual_fields(self):
        self._make_image(title_bs='Photo')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item = self._results(resp)[0]
        for field in ['title_bs', 'title_en', 'description_bs', 'description_en',
                      'alt_text_bs', 'alt_text_en', 'caption_bs', 'caption_en']:
            self.assertNotIn(field, item)

    # 13. Response does not include admin-only fields.
    def test_no_admin_only_fields(self):
        self._make_image(title_bs='Photo')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item = self._results(resp)[0]
        for field in ['is_published', 'updated_at', 'provider_public_id', 'file_size']:
            self.assertNotIn(field, item)

    # 14. Response does not include a full nested album object.
    def test_no_nested_album_object(self):
        self._make_image(title_bs='Photo')
        resp = self.client.get(_PUBLIC_ALBUM_MEDIA_URL.format(self.album.slug))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item = self._results(resp)[0]
        self.assertNotIn('album', item)
        self.assertIn('album_slug', item)
