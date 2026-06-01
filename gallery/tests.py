import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from .models import Album, MediaItem

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


