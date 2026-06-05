from rest_framework import serializers

from .models import Album, FieldNote, MediaItem, Tag, VideoClip, VisitorMessage

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


# ---------------------------------------------------------------------------
# Tag serializers
# ---------------------------------------------------------------------------

class TagSerializer(serializers.ModelSerializer):
    """Read serializer for tags (public and admin)."""

    class Meta:
        model = Tag
        fields = ['id', 'name_bs', 'name_en', 'slug']


class TagWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating/updating tags (admin only)."""

    slug = serializers.SlugField(required=False, allow_blank=False)

    class Meta:
        model = Tag
        fields = ['id', 'name_bs', 'name_en', 'slug', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'name_bs': {'required': True, 'allow_blank': False},
        }

    def validate(self, data):
        from django.utils.text import slugify as _slugify

        if self.instance is None and not data.get('slug'):
            data['slug'] = _slugify(data['name_bs'])

        slug = data.get('slug')
        if slug:
            qs = Tag.objects.filter(slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'slug': f'A tag with slug "{slug}" already exists.'}
                )

        return data


class _TagsM2MMixin:
    """Mixin for ModelSerializers that have a writable ``tags`` M2M field."""

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        instance = super().create(validated_data)
        if tags is not None:
            instance.tags.set(tags)
        return instance

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        instance = super().update(instance, validated_data)
        if tags is not None:
            instance.tags.set(tags)
        return instance


class AlbumWriteSerializer(_TagsM2MMixin, serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=False)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

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
            'tags',
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
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'slug', 'title', 'description', 'display_order', 'cover', 'tags']

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
    tags = TagSerializer(many=True, read_only=True)

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
            'tags',
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
    tags = TagSerializer(many=True, read_only=True)

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
            'tags',
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


# ===========================================================================
# Admin-only serializers
# ===========================================================================

class AdminImageGallerySerializer(serializers.ModelSerializer):
    """Read serializer for admin image gallery list/detail. Includes image count."""

    cover = MediaCoverSerializer(source='cover_media', read_only=True)
    # Populated by annotated queryset in the view.
    image_count = serializers.IntegerField(read_only=True, default=0)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = [
            'id',
            'slug',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'is_published',
            'display_order',
            'image_count',
            'cover',
            'tags',
            'created_at',
            'updated_at',
        ]


class AdminImageGalleryWriteSerializer(_TagsM2MMixin, serializers.ModelSerializer):
    """Write serializer for creating/updating image galleries (admin only).

    Identical validation logic to AlbumWriteSerializer.
    gallery_type='image' is set by the view on create/update.
    """

    slug = serializers.SlugField(required=False, allow_blank=False)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

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
            'tags',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'title_bs': {'required': True, 'allow_blank': False},
        }

    def validate(self, data):
        from django.utils.text import slugify

        if self.instance is None and not data.get('slug'):
            data['slug'] = slugify(data['title_bs'])

        slug = data.get('slug')
        if slug:
            qs = Album.objects.filter(slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'slug': f'An album with slug "{slug}" already exists.'}
                )

        is_published = data.get('is_published', getattr(self.instance, 'is_published', False))
        title_bs = data.get('title_bs', getattr(self.instance, 'title_bs', ''))
        if is_published and not title_bs:
            raise serializers.ValidationError(
                {'title_bs': 'title_bs is required for published galleries.'}
            )

        return data


class AdminVideoGallerySerializer(serializers.ModelSerializer):
    """Read serializer for admin video gallery list/detail. Includes per-status video counts."""

    cover = MediaCoverSerializer(source='cover_media', read_only=True)
    # Populated by annotated queryset in the view.
    video_count = serializers.IntegerField(read_only=True, default=0)
    ready_video_count = serializers.IntegerField(read_only=True, default=0)
    processing_video_count = serializers.IntegerField(read_only=True, default=0)
    failed_video_count = serializers.IntegerField(read_only=True, default=0)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Album
        fields = [
            'id',
            'slug',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'is_published',
            'display_order',
            'video_count',
            'ready_video_count',
            'processing_video_count',
            'failed_video_count',
            'cover',
            'tags',
            'created_at',
            'updated_at',
        ]


class AdminVideoGalleryWriteSerializer(_TagsM2MMixin, serializers.ModelSerializer):
    """Write serializer for creating/updating video galleries (admin only).

    gallery_type='video' is set by the view on create/update.
    """

    slug = serializers.SlugField(required=False, allow_blank=False)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

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
            'tags',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'title_bs': {'required': True, 'allow_blank': False},
        }

    def validate(self, data):
        from django.utils.text import slugify

        if self.instance is None and not data.get('slug'):
            data['slug'] = slugify(data['title_bs'])

        slug = data.get('slug')
        if slug:
            qs = Album.objects.filter(slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'slug': f'An album with slug "{slug}" already exists.'}
                )

        is_published = data.get('is_published', getattr(self.instance, 'is_published', False))
        title_bs = data.get('title_bs', getattr(self.instance, 'title_bs', ''))
        if is_published and not title_bs:
            raise serializers.ValidationError(
                {'title_bs': 'title_bs is required for published galleries.'}
            )

        return data


class AdminImageItemSerializer(serializers.ModelSerializer):
    """Read serializer for admin image item list/detail."""

    gallery_id = serializers.IntegerField(source='album_id', read_only=True)
    gallery_slug = serializers.SlugRelatedField(
        source='album', slug_field='slug', read_only=True
    )
    gallery_title_bs = serializers.CharField(source='album.title_bs', read_only=True)

    class Meta:
        model = MediaItem
        fields = [
            'id',
            'gallery_id',
            'gallery_slug',
            'gallery_title_bs',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'provider_public_id',
            'public_url',
            'thumbnail_url',
            'is_published',
            'display_order',
            'width',
            'height',
            'file_size',
            'created_at',
            'updated_at',
        ]


class AdminImageItemWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating/updating image items (admin only).

    On create: ``album`` (PK of an image gallery) and ``original_file`` are required.
    On patch:  both are optional.
    """

    album = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.filter(gallery_type=Album.GALLERY_TYPE_IMAGE),
        required=False,
    )
    original_file = serializers.ImageField(required=False)

    def validate_original_file(self, file):
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
            'album',
            'original_file',
            'title_bs',
            'description_bs',
            'alt_text_bs',
            'caption_bs',
            'title_en',
            'description_en',
            'alt_text_en',
            'caption_en',
            'tags',
            'display_order',
            'is_published',
            'provider',
            'public_url',
            'thumbnail_url',
            'provider_public_id',
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
        if self.instance is None:
            if not data.get('album'):
                raise serializers.ValidationError(
                    {'album': 'An image gallery (album) is required.'}
                )
            if not data.get('original_file'):
                raise serializers.ValidationError(
                    {'original_file': 'An image file is required.'}
                )

        is_published = data.get('is_published', getattr(self.instance, 'is_published', False))
        alt_text_bs = data.get('alt_text_bs', getattr(self.instance, 'alt_text_bs', ''))
        if is_published and not alt_text_bs:
            raise serializers.ValidationError(
                {'alt_text_bs': 'alt_text_bs is required when is_published is True.'}
            )

        return data


class AdminVideoItemSerializer(serializers.ModelSerializer):
    """Read serializer for admin video item list/detail.

    Maps ``is_public`` (model field) to ``is_published`` for consistent admin API naming.
    """

    gallery_id = serializers.IntegerField(source='album_id', read_only=True)
    gallery_slug = serializers.SlugRelatedField(
        source='album', slug_field='slug', read_only=True
    )
    gallery_title_bs = serializers.CharField(
        source='album.title_bs', read_only=True, default=''
    )
    is_published = serializers.BooleanField(source='is_public', read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = VideoClip
        fields = [
            'id',
            'gallery_id',
            'gallery_slug',
            'gallery_title_bs',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'cloudflare_uid',
            'cloudflare_thumbnail_url',
            'cloudflare_playback_url',
            'duration_seconds',
            'status',
            'is_published',
            'tags',
            'created_at',
            'updated_at',
        ]


class AdminVideoItemWriteSerializer(_TagsM2MMixin, serializers.ModelSerializer):
    """Write serializer for updating video items (admin PATCH only).

    Maps incoming ``is_published`` to model ``is_public``.
    Cloudflare-managed fields (uid, urls, status, duration) are read-only.
    """

    album = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.filter(gallery_type=Album.GALLERY_TYPE_VIDEO),
        required=False,
        allow_null=True,
    )
    is_published = serializers.BooleanField(source='is_public', required=False)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = VideoClip
        fields = [
            'id',
            'album',
            'title_bs',
            'title_en',
            'description_bs',
            'description_en',
            'is_published',
            'tags',
            'cloudflare_uid',
            'cloudflare_thumbnail_url',
            'cloudflare_playback_url',
            'duration_seconds',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'cloudflare_uid',
            'cloudflare_thumbnail_url',
            'cloudflare_playback_url',
            'duration_seconds',
            'status',
            'created_at',
            'updated_at',
        ]


class AdminVideoDirectUploadSerializer(serializers.Serializer):
    """Request body for POST /admin/videos/direct-upload/.

    album must be a video-type gallery.
    """

    album = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.filter(gallery_type=Album.GALLERY_TYPE_VIDEO),
        required=False,
        allow_null=True,
        default=None,
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


class AdminVideoCompleteUploadSerializer(serializers.Serializer):
    """Request body for POST /admin/videos/complete-upload/.

    Marks a VideoClip as 'processing' once the frontend has finished
    uploading to Cloudflare Stream directly.
    Accepts either ``video_id`` (PK) or ``cloudflare_uid`` to identify the record.
    """

    video_id = serializers.IntegerField(required=False, allow_null=True)
    cloudflare_uid = serializers.CharField(max_length=128, required=False, allow_blank=False)

    def validate(self, data):
        if not data.get('video_id') and not data.get('cloudflare_uid'):
            raise serializers.ValidationError(
                'Provide either video_id or cloudflare_uid.'
            )
        return data


# ---------------------------------------------------------------------------
# Public hero-video serializer
# ---------------------------------------------------------------------------

class HeroVideoSerializer(serializers.ModelSerializer):
    album_title_bs = serializers.SerializerMethodField()
    album_title_en = serializers.SerializerMethodField()

    class Meta:
        model = VideoClip
        fields = [
            'id',
            'title_bs',
            'title_en',
            'album_id',
            'album_title_bs',
            'album_title_en',
            'duration_seconds',
            'cloudflare_uid',
            'cloudflare_playback_url',
            'cloudflare_thumbnail_url',
        ]

    def get_album_title_bs(self, obj):
        if obj.album is None:
            return ''
        return obj.album.title_bs

    def get_album_title_en(self, obj):
        if obj.album is None:
            return ''
        return obj.album.title_en


class VisitorMessageCreateSerializer(serializers.ModelSerializer):
    """Write serializer for public visitor message submission."""

    sender_name = serializers.CharField(max_length=120, allow_blank=False)
    sender_email = serializers.EmailField(max_length=254)
    subject = serializers.CharField(max_length=180, allow_blank=False)
    message = serializers.CharField(allow_blank=False)
    video_id = serializers.PrimaryKeyRelatedField(
        queryset=VideoClip.objects.all(),
        required=False,
        allow_null=True,
        source='video',
    )
    timestamp_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    class Meta:
        model = VisitorMessage
        fields = [
            'id', 'sender_name', 'sender_email', 'subject', 'message',
            'video_id', 'timestamp_seconds', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_sender_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('This field may not be blank.')
        return value

    def validate_subject(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('This field may not be blank.')
        return value

    def validate_message(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('This field may not be blank.')
        return value

