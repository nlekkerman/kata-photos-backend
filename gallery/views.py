from rest_framework import generics

from .models import Album, MediaItem
from .serializers import (
    AlbumDetailSerializer,
    AlbumListSerializer,
    MediaItemPublicSerializer,
)


class AlbumListView(generics.ListAPIView):
    serializer_class = AlbumListSerializer

    def get_queryset(self):
        return Album.objects.filter(is_published=True)


class AlbumDetailView(generics.RetrieveAPIView):
    serializer_class = AlbumDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Album.objects.filter(is_published=True)


class AlbumMediaListView(generics.ListAPIView):
    serializer_class = MediaItemPublicSerializer

    def get_queryset(self):
        album = generics.get_object_or_404(
            Album, slug=self.kwargs['slug'], is_published=True
        )
        return MediaItem.objects.filter(album=album, is_published=True)


class MediaItemDetailView(generics.RetrieveAPIView):
    serializer_class = MediaItemPublicSerializer

    def get_queryset(self):
        return MediaItem.objects.filter(
            is_published=True, album__is_published=True
        )

