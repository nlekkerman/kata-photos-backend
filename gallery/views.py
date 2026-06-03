import io
import logging

from django.conf import settings
from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response


class CloudflareServiceError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Image upload to Cloudflare Images failed.'
    default_code = 'cloudflare_upload_error'

logger = logging.getLogger(__name__)

from .models import Album, FieldNote, MediaItem, VideoClip
from .serializers import (
    AdminImageGallerySerializer,
    AdminImageGalleryWriteSerializer,
    AdminImageItemSerializer,
    AdminImageItemWriteSerializer,
    AdminVideoCompleteUploadSerializer,
    AdminVideoDirectUploadSerializer,
    AdminVideoGallerySerializer,
    AdminVideoGalleryWriteSerializer,
    AdminVideoItemSerializer,
    AdminVideoItemWriteSerializer,
    AlbumCoverWriteSerializer,
    AlbumDetailSerializer,
    AlbumListSerializer,
    AlbumWriteSerializer,
    FieldNoteDetailSerializer,
    FieldNoteListSerializer,
    MediaItemPublicSerializer,
    MediaItemWriteSerializer,
    VideoClipDirectUploadRequestSerializer,
    VideoClipSerializer,
)

_ALLOWED_LANGS = ('en', 'bs')


class LangContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        raw_lang = self.request.query_params.get('lang', 'en').lower()
        context['lang'] = raw_lang if raw_lang in _ALLOWED_LANGS else 'en'
        return context


class AlbumListCreateView(LangContextMixin, generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AlbumWriteSerializer
        return AlbumListSerializer

    def get_queryset(self):
        if self.request.method == 'POST':
            return Album.objects.all()
        return Album.objects.filter(is_published=True)


class AlbumRetrieveUpdateDestroyView(LangContextMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = 'slug'
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.request.method in ('PATCH', 'DELETE'):
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AlbumWriteSerializer
        return AlbumDetailSerializer

    def get_queryset(self):
        if self.request.method in ('PATCH', 'DELETE'):
            return Album.objects.all()
        return Album.objects.filter(is_published=True)


class AlbumMediaListCreateView(LangContextMixin, generics.ListCreateAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MediaItemWriteSerializer
        return MediaItemPublicSerializer

    def get_queryset(self):
        album = generics.get_object_or_404(
            Album, slug=self.kwargs['slug'], is_published=True
        )
        return MediaItem.objects.filter(album=album, is_published=True)

    def perform_create(self, serializer):
        album = generics.get_object_or_404(Album, slug=self.kwargs['slug'])
        _save_media_item_with_cloudflare(serializer, album=album)


class MediaItemRetrieveUpdateDestroyView(LangContextMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = 'pk'
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ('PATCH', 'DELETE'):
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return MediaItemWriteSerializer
        return MediaItemPublicSerializer

    def get_queryset(self):
        if self.request.method in ('PATCH', 'DELETE'):
            return MediaItem.objects.all()
        return MediaItem.objects.filter(is_published=True, album__is_published=True)


class AlbumCoverUpdateView(LangContextMixin, generics.GenericAPIView):
    permission_classes = [IsAdminUser]
    http_method_names = ['patch', 'head', 'options']

    def patch(self, request, slug):
        album = generics.get_object_or_404(Album, slug=slug)
        serializer = AlbumCoverWriteSerializer(
            data=request.data,
            context={'request': request, 'album': album},
        )
        serializer.is_valid(raise_exception=True)
        updated_album = serializer.save()
        context = self.get_serializer_context()
        return Response(AlbumDetailSerializer(updated_album, context=context).data)


class FieldNoteListView(LangContextMixin, generics.ListAPIView):
    serializer_class = FieldNoteListSerializer

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)


class FieldNoteDetailView(LangContextMixin, generics.RetrieveAPIView):
    serializer_class = FieldNoteDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)


class VideoClipDirectUploadView(generics.GenericAPIView):
    """Staff-only endpoint: request a Cloudflare Stream direct-upload URL."""

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request):
        req_serializer = VideoClipDirectUploadRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        account_id = settings.CLOUDFLARE_ACCOUNT_ID
        api_token = settings.CLOUDFLARE_STREAM_API_TOKEN
        expiry_seconds = settings.CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
        watermark_uid = getattr(settings, "CLOUDFLARE_STREAM_WATERMARK_UID", "")

        if not account_id or not api_token:
            raise APIException(
                detail="Cloudflare Stream is not configured on this server.",
                code="stream_not_configured",
            )

        from .services.cloudflare_stream import (
            CloudflareStreamUploadError,
            create_direct_upload,
        )

        try:
            cf_result = create_direct_upload(
                account_id=account_id,
                api_token=api_token,
                max_duration_seconds=data['max_duration_seconds'],
                expiry_seconds=expiry_seconds,
                watermark_uid=watermark_uid,
            )
        except CloudflareStreamUploadError as exc:
            logger.error(
                "Cloudflare Stream upload error on %s: %s",
                request.path,
                exc,
            )
            raise CloudflareServiceError(detail=str(exc))

        video = VideoClip.objects.create(
            album=data.get('album'),
            title_bs=data['title_bs'],
            title_en=data.get('title_en', ''),
            description_bs=data.get('description_bs', ''),
            description_en=data.get('description_en', ''),
            cloudflare_uid=cf_result['uid'],
            status=VideoClip.STATUS_UPLOADING,
        )

        return Response(
            {
                "video": VideoClipSerializer(video).data,
                "upload_url": cf_result['upload_url'],
            },
            status=status.HTTP_201_CREATED,
        )


class VideoClipListView(generics.ListAPIView):
    """Public/admin video list.

    Public users see only ``is_public=True`` and ``status='ready'`` clips.
    Staff/admin users see all clips.
    Supports optional ``?album=<pk>`` filter.
    """

    serializer_class = VideoClipSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = VideoClip.objects.select_related('album').all()
        user = self.request.user
        if not (user and user.is_authenticated and user.is_staff):
            qs = qs.filter(is_public=True, status=VideoClip.STATUS_READY)
        album_pk = self.request.query_params.get('album')
        if album_pk:
            qs = qs.filter(album_id=album_pk)
        return qs


class VideoClipDetailView(generics.RetrieveAPIView):
    """Public/admin single video detail.

    Public users can only retrieve ``is_public=True`` and ``status='ready'`` clips.
    Staff/admin users can retrieve any clip.
    """

    serializer_class = VideoClipSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and user.is_staff:
            return VideoClip.objects.select_related('album').all()
        return VideoClip.objects.select_related('album').filter(
            is_public=True, status=VideoClip.STATUS_READY
        )


class VideoClipSyncView(generics.GenericAPIView):
    """Staff-only endpoint: sync a VideoClip with live Cloudflare Stream metadata.

    Updates ``status``, ``duration_seconds``, ``cloudflare_playback_url``, and
    ``cloudflare_thumbnail_url`` from the Cloudflare API response.
    Returns the updated serialized ``VideoClip``.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request, pk):
        video = generics.get_object_or_404(VideoClip, pk=pk)

        account_id = settings.CLOUDFLARE_ACCOUNT_ID
        api_token = settings.CLOUDFLARE_STREAM_API_TOKEN
        customer_subdomain = settings.CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN

        if not account_id or not api_token:
            raise APIException(
                detail="Cloudflare Stream is not configured on this server.",
                code="stream_not_configured",
            )

        from .services.cloudflare_stream import (
            CloudflareStreamError,
            build_playback_url,
            build_thumbnail_url,
            get_video_details,
            map_cloudflare_status,
        )

        try:
            cf = get_video_details(
                account_id=account_id,
                api_token=api_token,
                uid=video.cloudflare_uid,
            )
        except CloudflareStreamError as exc:
            logger.error(
                "Cloudflare Stream sync error for VideoClip pk=%s: %s",
                video.pk,
                exc,
            )
            raise CloudflareServiceError(detail=str(exc))

        update_fields = []

        new_status = map_cloudflare_status(cf)
        if video.status != new_status:
            video.status = new_status
            update_fields.append('status')

        raw_duration = cf.get('duration')
        if raw_duration is not None and raw_duration >= 0:
            new_duration = round(raw_duration)
            if video.duration_seconds != new_duration:
                video.duration_seconds = new_duration
                update_fields.append('duration_seconds')

        if customer_subdomain:
            new_playback = build_playback_url(
                customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
            )
            if video.cloudflare_playback_url != new_playback:
                video.cloudflare_playback_url = new_playback
                update_fields.append('cloudflare_playback_url')

            new_thumbnail = build_thumbnail_url(
                customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
            )
            if video.cloudflare_thumbnail_url != new_thumbnail:
                video.cloudflare_thumbnail_url = new_thumbnail
                update_fields.append('cloudflare_thumbnail_url')

        if update_fields:
            video.save(update_fields=update_fields)

        return Response(VideoClipSerializer(video).data)


# ===========================================================================
# Shared helper: Cloudflare Images upload (used by both legacy and admin views)
# ===========================================================================

def _save_media_item_with_cloudflare(serializer, *, album, extra_save_kwargs=None):
    """Upload an image to Cloudflare Images if configured, else save locally.

    ``serializer`` must already be validated.
    ``album`` is the Album instance to associate with the MediaItem.
    ``extra_save_kwargs`` are merged into the ``serializer.save()`` call.
    """
    from PIL import Image as PilImage

    from .services.cloudflare_images import CloudflareUploadError, upload_image

    extra = extra_save_kwargs or {}
    cf_account_id = settings.CLOUDFLARE_ACCOUNT_ID
    cf_token = settings.CLOUDFLARE_IMAGES_API_TOKEN

    if not (cf_account_id and cf_token and serializer.validated_data.get('original_file')):
        serializer.save(album=album, provider='local', media_type='image', **extra)
        return

    uploaded_file = serializer.validated_data['original_file']
    raw = uploaded_file.file
    raw.seek(0)
    file_bytes = raw.read()
    file_size = len(file_bytes)

    width = height = None
    try:
        with PilImage.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size
    except Exception:
        pass

    try:
        cf_result = upload_image(
            file_bytes,
            filename=uploaded_file.name,
            content_type=uploaded_file.content_type,
            account_id=cf_account_id,
            api_token=cf_token,
        )
    except CloudflareUploadError as exc:
        raise CloudflareServiceError(detail=str(exc))

    serializer.save(
        album=album,
        provider='cloudflare_images',
        provider_public_id=cf_result['cf_id'],
        public_url=cf_result['public_url'],
        thumbnail_url=cf_result['thumbnail_url'],
        original_file=None,
        width=width,
        height=height,
        file_size=file_size,
        media_type='image',
        **extra,
    )


# ===========================================================================
# Admin-only views
# ===========================================================================

def _image_gallery_queryset():
    return Album.objects.filter(gallery_type=Album.GALLERY_TYPE_IMAGE).annotate(
        image_count=Count(
            'media_items',
            filter=Q(media_items__media_type='image'),
        )
    )


def _video_gallery_queryset():
    return Album.objects.filter(gallery_type=Album.GALLERY_TYPE_VIDEO).annotate(
        video_count=Count('videos'),
        ready_video_count=Count('videos', filter=Q(videos__status='ready')),
        processing_video_count=Count('videos', filter=Q(videos__status='processing')),
        failed_video_count=Count('videos', filter=Q(videos__status='failed')),
    )


class AdminImageGalleryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/gallery/admin/image-galleries/  — list all image galleries (admin).
    POST /api/gallery/admin/image-galleries/  — create an image gallery (admin).
    """

    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return _image_gallery_queryset()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminImageGalleryWriteSerializer
        return AdminImageGallerySerializer

    def perform_create(self, serializer):
        serializer.save(gallery_type=Album.GALLERY_TYPE_IMAGE)


class AdminImageGalleryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/gallery/admin/image-galleries/<id>/  — retrieve image gallery (admin).
    PATCH  /api/gallery/admin/image-galleries/<id>/  — update image gallery (admin).
    DELETE /api/gallery/admin/image-galleries/<id>/  — delete image gallery (admin).
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return _image_gallery_queryset()

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminImageGalleryWriteSerializer
        return AdminImageGallerySerializer

    def perform_update(self, serializer):
        serializer.save(gallery_type=Album.GALLERY_TYPE_IMAGE)


class AdminImageItemListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/gallery/admin/images/?gallery=<id>  — list images (admin, optionally filtered).
    POST /api/gallery/admin/images/               — upload an image to an image gallery (admin).
    """

    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = MediaItem.objects.filter(
            media_type='image',
            album__gallery_type=Album.GALLERY_TYPE_IMAGE,
        ).select_related('album')
        gallery_id = self.request.query_params.get('gallery')
        if gallery_id:
            qs = qs.filter(album_id=gallery_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminImageItemWriteSerializer
        return AdminImageItemSerializer

    def perform_create(self, serializer):
        album = serializer.validated_data['album']
        _save_media_item_with_cloudflare(serializer, album=album)


class AdminImageItemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/gallery/admin/images/<pk>/  — update image metadata (admin).
    DELETE /api/gallery/admin/images/<pk>/  — delete image (admin).
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return MediaItem.objects.filter(
            media_type='image',
            album__gallery_type=Album.GALLERY_TYPE_IMAGE,
        ).select_related('album')

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminImageItemWriteSerializer
        return AdminImageItemSerializer


class AdminVideoGalleryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/gallery/admin/video-galleries/  — list all video galleries (admin).
    POST /api/gallery/admin/video-galleries/  — create a video gallery (admin).
    """

    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return _video_gallery_queryset()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminVideoGalleryWriteSerializer
        return AdminVideoGallerySerializer

    def perform_create(self, serializer):
        serializer.save(gallery_type=Album.GALLERY_TYPE_VIDEO)


class AdminVideoGalleryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/gallery/admin/video-galleries/<id>/  — retrieve video gallery (admin).
    PATCH  /api/gallery/admin/video-galleries/<id>/  — update video gallery (admin).
    DELETE /api/gallery/admin/video-galleries/<id>/  — delete video gallery (admin).
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return _video_gallery_queryset()

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminVideoGalleryWriteSerializer
        return AdminVideoGallerySerializer

    def perform_update(self, serializer):
        serializer.save(gallery_type=Album.GALLERY_TYPE_VIDEO)


class AdminVideoItemListView(generics.ListAPIView):
    """
    GET /api/gallery/admin/videos/?gallery=<id>  — list videos for admin (all statuses).
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminVideoItemSerializer

    def get_queryset(self):
        qs = VideoClip.objects.select_related('album').all()
        gallery_id = self.request.query_params.get('gallery')
        if gallery_id:
            qs = qs.filter(album_id=gallery_id)
        return qs


class AdminVideoDirectUploadView(generics.GenericAPIView):
    """
    POST /api/gallery/admin/videos/direct-upload/

    Request a Cloudflare Stream direct-upload URL (admin only).
    Creates a VideoClip record with status='uploading' and returns the upload URL.
    album must be a video-type gallery if provided.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request):
        req_serializer = AdminVideoDirectUploadSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        account_id = settings.CLOUDFLARE_ACCOUNT_ID
        api_token = settings.CLOUDFLARE_STREAM_API_TOKEN
        expiry_seconds = settings.CLOUDFLARE_STREAM_DIRECT_UPLOAD_EXPIRY_SECONDS
        watermark_uid = getattr(settings, "CLOUDFLARE_STREAM_WATERMARK_UID", "")

        if not account_id or not api_token:
            raise APIException(
                detail="Cloudflare Stream is not configured on this server.",
                code="stream_not_configured",
            )

        from .services.cloudflare_stream import (
            CloudflareStreamUploadError,
            create_direct_upload,
        )

        try:
            cf_result = create_direct_upload(
                account_id=account_id,
                api_token=api_token,
                max_duration_seconds=data['max_duration_seconds'],
                expiry_seconds=expiry_seconds,
                watermark_uid=watermark_uid,
            )
        except CloudflareStreamUploadError as exc:
            logger.error(
                "Cloudflare Stream upload error on %s: %s",
                request.path,
                exc,
            )
            raise CloudflareServiceError(detail=str(exc))

        video = VideoClip.objects.create(
            album=data.get('album'),
            title_bs=data['title_bs'],
            title_en=data.get('title_en', ''),
            description_bs=data.get('description_bs', ''),
            description_en=data.get('description_en', ''),
            cloudflare_uid=cf_result['uid'],
            status=VideoClip.STATUS_UPLOADING,
        )

        return Response(
            {
                "video": AdminVideoItemSerializer(video).data,
                "upload_url": cf_result['upload_url'],
            },
            status=status.HTTP_201_CREATED,
        )


class AdminVideoCompleteUploadView(generics.GenericAPIView):
    """
    POST /api/gallery/admin/videos/complete-upload/

    Marks a VideoClip as 'processing' once the frontend has uploaded
    the file directly to Cloudflare Stream.

    Accepts ``video_id`` (PK) or ``cloudflare_uid`` to identify the record.
    Does not contact Cloudflare — status will be updated to 'ready'/'failed'
    via a subsequent refresh-status call once Cloudflare finishes processing.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request):
        req_serializer = AdminVideoCompleteUploadSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        if data.get('video_id'):
            video = generics.get_object_or_404(VideoClip, pk=data['video_id'])
        else:
            video = generics.get_object_or_404(
                VideoClip, cloudflare_uid=data['cloudflare_uid']
            )

        if video.status == VideoClip.STATUS_UPLOADING:
            video.status = VideoClip.STATUS_PROCESSING
            video.save(update_fields=['status'])

        return Response(AdminVideoItemSerializer(video).data, status=status.HTTP_200_OK)


class AdminVideoItemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/gallery/admin/videos/<pk>/  — retrieve video (admin).
    PATCH  /api/gallery/admin/videos/<pk>/  — update video metadata (admin).
    DELETE /api/gallery/admin/videos/<pk>/  — delete video record (admin).

    Note: DELETE removes only the Django record. Cloudflare Stream asset is NOT
    automatically deleted. Use the Cloudflare dashboard or API for that.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    queryset = VideoClip.objects.select_related('album').all()

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminVideoItemWriteSerializer
        return AdminVideoItemSerializer


class AdminVideoRefreshStatusView(generics.GenericAPIView):
    """
    POST /api/gallery/admin/videos/<pk>/refresh-status/

    Syncs a VideoClip with live Cloudflare Stream metadata.
    Updates status, duration, playback URL, and thumbnail URL.
    Alias that delegates to the existing VideoClipSyncView logic.
    """

    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request, pk):
        video = generics.get_object_or_404(VideoClip, pk=pk)

        account_id = settings.CLOUDFLARE_ACCOUNT_ID
        api_token = settings.CLOUDFLARE_STREAM_API_TOKEN
        customer_subdomain = settings.CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN

        if not account_id or not api_token:
            raise APIException(
                detail="Cloudflare Stream is not configured on this server.",
                code="stream_not_configured",
            )

        from .services.cloudflare_stream import (
            CloudflareStreamError,
            build_playback_url,
            build_thumbnail_url,
            get_video_details,
            map_cloudflare_status,
        )

        try:
            cf = get_video_details(
                account_id=account_id,
                api_token=api_token,
                uid=video.cloudflare_uid,
            )
        except CloudflareStreamError as exc:
            logger.error(
                "Cloudflare Stream refresh-status error for VideoClip pk=%s: %s",
                video.pk,
                exc,
            )
            raise CloudflareServiceError(detail=str(exc))

        update_fields = []

        new_status = map_cloudflare_status(cf)
        if video.status != new_status:
            video.status = new_status
            update_fields.append('status')

        raw_duration = cf.get('duration')
        if raw_duration is not None and raw_duration >= 0:
            new_duration = round(raw_duration)
            if video.duration_seconds != new_duration:
                video.duration_seconds = new_duration
                update_fields.append('duration_seconds')

        if customer_subdomain:
            new_playback = build_playback_url(
                customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
            )
            if video.cloudflare_playback_url != new_playback:
                video.cloudflare_playback_url = new_playback
                update_fields.append('cloudflare_playback_url')

            new_thumbnail = build_thumbnail_url(
                customer_subdomain=customer_subdomain, uid=video.cloudflare_uid
            )
            if video.cloudflare_thumbnail_url != new_thumbnail:
                video.cloudflare_thumbnail_url = new_thumbnail
                update_fields.append('cloudflare_thumbnail_url')

        if update_fields:
            video.save(update_fields=update_fields)

        return Response(AdminVideoItemSerializer(video).data)

