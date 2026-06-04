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
