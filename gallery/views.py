import io

from django.conf import settings
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response


class CloudflareServiceError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Image upload to Cloudflare Images failed.'
    default_code = 'cloudflare_upload_error'

from .models import Album, FieldNote, MediaItem, VideoClip
from .serializers import (
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

        cf_account_id = settings.CLOUDFLARE_ACCOUNT_ID
        cf_token = settings.CLOUDFLARE_IMAGES_API_TOKEN

        if cf_account_id and cf_token and serializer.validated_data.get('original_file'):
            self._perform_create_cloudflare(serializer, album, cf_account_id, cf_token)
        else:
            serializer.save(album=album, provider='local')

    def _perform_create_cloudflare(self, serializer, album, account_id, api_token):
        from PIL import Image as PilImage

        from .services.cloudflare_images import CloudflareUploadError, upload_image

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
                account_id=account_id,
                api_token=api_token,
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
        )


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
            )
        except CloudflareStreamUploadError as exc:
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

