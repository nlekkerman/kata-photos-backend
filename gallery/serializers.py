from rest_framework import serializers

from .models import Album, MediaItem


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

    class Meta:
        model = MediaItem
        fields = ['id', 'thumbnail_url', 'alt_text']

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        return _get_thumbnail_url(obj, request)


class AlbumListSerializer(serializers.ModelSerializer):
    cover = MediaCoverSerializer(source='cover_media', read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'slug', 'title', 'description', 'display_order', 'cover']


class AlbumDetailSerializer(serializers.ModelSerializer):
    cover = MediaCoverSerializer(source='cover_media', read_only=True)

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


class MediaItemPublicSerializer(serializers.ModelSerializer):
    album_slug = serializers.SlugRelatedField(source='album', slug_field='slug', read_only=True)
    public_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

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
