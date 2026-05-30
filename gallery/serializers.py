from rest_framework import serializers

from .models import Album, FieldNote, MediaItem


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
