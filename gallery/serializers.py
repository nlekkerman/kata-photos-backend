from rest_framework import serializers

from .models import Album, FieldNote, MediaItem, VideoClip

# ---------------------------------------------------------------------------
# Upload safety constants (Phase 6)
# ---------------------------------------------------------------------------
MAX_IMAGE_UPLOAD_SIZE_MB = 10
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def resolve_translated(obj, field_name, lang):
    value = getattr(obj, f"{field_name}_{lang}", "")
    fallback = getattr(obj, f"{field_name}_en", "")
    return value or fallback


def _resolve_local_url(file_field, request):
    if not file_field or not getattr(file_field, 'name', ''):
        return ''
    relative = file_field.url
    if request is not None:
        return request.build_absolute_uri(relative)
    return relative


def _get_public_url(obj, request):
    if obj.provider == 'local':
        return _resolve_local_url(obj.original_file, request)
    return obj.public_url


def _get_thumbnail_url(obj, request):
    if obj.provider == 'local':
        return _resolve_local_url(obj.original_file, request)
    return obj.thumbnail_url


class AlbumWriteSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=False)

    class Meta:
        model = Album
        fields = [
            'id',
            'slug',
            'title_bs',
            'description_bs',
            'seo_title_bs',
            'seo_description_bs',
            'title_en',
            'description_en',
            'seo_title_en',
            'seo_description_en',
            'display_order',
            'is_published',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'title_bs': {'required': True, 'allow_blank': False},
        }

    def validate(self, data):
        from django.utils.text import slugify

        # Auto-generate slug from title_bs on create only
        if self.instance is None and not data.get('slug'):
            data['slug'] = slugify(data['title_bs'])

        # Check for duplicate slug
        slug = data.get('slug')
        if slug:
            qs = Album.objects.filter(slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'slug': f'An album with slug "{slug}" already exists.'}
                )

        # Published albums require title_bs
        is_published = data.get('is_published', getattr(self.instance, 'is_published', False))
        title_bs = data.get('title_bs', getattr(self.instance, 'title_bs', ''))
        if is_published and not title_bs:
            raise serializers.ValidationError(
                {'title_bs': 'title_bs is required for published albums.'}
            )

        return data


class MediaItemWriteSerializer(serializers.ModelSerializer):
    original_file = serializers.ImageField(required=False)

    def validate_original_file(self, file):
        """Reject files that are too large or have an unsupported content type."""
        max_bytes = MAX_IMAGE_UPLOAD_SIZE_MB * 1024 * 1024
        if file.size > max_bytes:
            raise serializers.ValidationError(
                f"Image file too large. Maximum allowed size is {MAX_IMAGE_UPLOAD_SIZE_MB} MB."
            )
        content_type = getattr(file, "content_type", None)
        if not content_type or content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_IMAGE_CONTENT_TYPES))
            raise serializers.ValidationError(
                f"Unsupported file type '{content_type}'. Allowed types: {allowed}."
            )
        return file

    class Meta:
        model = MediaItem
        fields = [
            'id',
            'original_file',
            'provider',
            'public_url',
            'thumbnail_url',
            'provider_public_id',
            'media_type',
            'title_bs',
            'caption_bs',
            'description_bs',
            'alt_text_bs',
            'title_en',
            'caption_en',
            'description_en',
            'alt_text_en',
            'tags',
            'display_order',
            'is_published',
            'width',
            'height',
            'file_size',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'provider', 'public_url', 'thumbnail_url', 'provider_public_id',
            'width', 'height', 'file_size', 'created_at', 'updated_at',
        ]

    def validate(self, data):
        # original_file is required when creating a new media item
        if self.instance is None and not data.get('original_file'):
            raise serializers.ValidationError(
                {'original_file': 'An image file is required.'}
            )

        # NOTE: Replacing original_file on PATCH leaves the previous file on disk.
        # Orphaned file cleanup should be handled in a future cleanup phase
        # (e.g., a pre_save signal or a periodic management command).

        # If is_published=True, alt_text_bs must be provided
        is_published = data.get('is_published', getattr(self.instance, 'is_published', False))
        alt_text_bs = data.get('alt_text_bs', getattr(self.instance, 'alt_text_bs', ''))
        if is_published and not alt_text_bs:
            raise serializers.ValidationError(
                {'alt_text_bs': 'alt_text_bs is required when is_published is True.'}
            )

        return data


class AlbumCoverWriteSerializer(serializers.Serializer):
    cover_media_id = serializers.IntegerField(allow_null=True)

    def validate(self, data):
        cover_media_id = data['cover_media_id']
        if cover_media_id is None:
            data['cover_media'] = None
            return data

        album = self.context['album']
        try:
            media = MediaItem.objects.get(pk=cover_media_id)
        except MediaItem.DoesNotExist:
            raise serializers.ValidationError(
                {'cover_media_id': f'Media item {cover_media_id} not found.'}
            )

        if media.album_id != album.pk:
            raise serializers.ValidationError(
                {'cover_media_id': 'Media item does not belong to this album.'}
            )
        if media.media_type != 'image':
            raise serializers.ValidationError(
                {'cover_media_id': 'Cover media must be an image.'}
            )
        if not media.is_published:
            raise serializers.ValidationError(
                {'cover_media_id': 'Cover media must be published.'}
            )

        data['cover_media'] = media
        return data

    def save(self):
        album = self.context['album']
        album.cover_media = self.validated_data['cover_media']
        album.save(update_fields=['cover_media'])
        return album


class MediaCoverSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    alt_text = serializers.SerializerMethodField()

    class Meta:
        model = MediaItem
        fields = ['id', 'thumbnail_url', 'alt_text']

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        return _get_thumbnail_url(obj, request)

    def get_alt_text(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'alt_text', lang)


class AlbumListSerializer(serializers.ModelSerializer):
    cover = MediaCoverSerializer(source='cover_media', read_only=True)
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = ['id', 'slug', 'title', 'description', 'display_order', 'cover']

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_description(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'description', lang)


class AlbumDetailSerializer(serializers.ModelSerializer):
    cover = MediaCoverSerializer(source='cover_media', read_only=True)
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    seo_title = serializers.SerializerMethodField()
    seo_description = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            'id',
            'slug',
            'title',
            'description',
            'seo_title',
            'seo_description',
            'display_order',
            'cover',
            'created_at',
        ]

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_description(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'description', lang)

    def get_seo_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'seo_title', lang)

    def get_seo_description(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'seo_description', lang)


class MediaItemPublicSerializer(serializers.ModelSerializer):
    album_slug = serializers.SlugRelatedField(source='album', slug_field='slug', read_only=True)
    public_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    alt_text = serializers.SerializerMethodField()
    caption = serializers.SerializerMethodField()

    class Meta:
        model = MediaItem
        fields = [
            'id',
            'album_slug',
            'media_type',
            'title',
            'description',
            'alt_text',
            'caption',
            'tags',
            'public_url',
            'thumbnail_url',
            'width',
            'height',
            'display_order',
        ]

    def get_public_url(self, obj):
        request = self.context.get('request')
        return _get_public_url(obj, request)

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        return _get_thumbnail_url(obj, request)

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_description(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'description', lang)

    def get_alt_text(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'alt_text', lang)

    def get_caption(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'caption', lang)


class FieldNoteCoverSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    alt_text = serializers.SerializerMethodField()

    class Meta:
        model = MediaItem
        fields = ['id', 'thumbnail_url', 'alt_text']

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        return _get_thumbnail_url(obj, request)

    def get_alt_text(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'alt_text', lang)


class FieldNoteListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    cover_image = FieldNoteCoverSerializer(read_only=True)

    class Meta:
        model = FieldNote
        fields = ['id', 'slug', 'title', 'excerpt', 'location', 'published_at', 'cover_image']

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_excerpt(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'excerpt', lang)


class FieldNoteDetailSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    cover_image = FieldNoteCoverSerializer(read_only=True)

    class Meta:
        model = FieldNote
        fields = ['id', 'slug', 'title', 'excerpt', 'body', 'location', 'published_at', 'cover_image']

    def get_title(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'title', lang)

    def get_excerpt(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'excerpt', lang)

    def get_body(self, obj):
        lang = self.context.get('lang', 'en')
        return resolve_translated(obj, 'body', lang)


# ---------------------------------------------------------------------------
# VideoClip serializers
# ---------------------------------------------------------------------------

class VideoClipSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoClip
        fields = [
            'id',
            'album',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'cloudflare_uid',
            'cloudflare_thumbnail_url',
            'cloudflare_playback_url',
            'duration_seconds',
            'status',
            'is_public',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'cloudflare_uid',
            'cloudflare_thumbnail_url',
            'cloudflare_playback_url',
            'status',
            'created_at',
            'updated_at',
        ]


class VideoClipDirectUploadRequestSerializer(serializers.Serializer):
    album = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.all(), required=False, allow_null=True, default=None
    )
    title_bs = serializers.CharField(max_length=255)
    title_en = serializers.CharField(max_length=255, allow_blank=True, default="")
    description_bs = serializers.CharField(allow_blank=True, default="")
    description_en = serializers.CharField(allow_blank=True, default="")
    max_duration_seconds = serializers.IntegerField(required=False, default=300)

    def validate_max_duration_seconds(self, value):
        if value <= 0:
            raise serializers.ValidationError("max_duration_seconds must be a positive integer.")
        return value

