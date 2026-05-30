from rest_framework import generics

from .models import Album, FieldNote, MediaItem
from .serializers import (
    AlbumDetailSerializer,
    AlbumListSerializer,
    FieldNoteDetailSerializer,
    FieldNoteListSerializer,
    MediaItemPublicSerializer,
)

_ALLOWED_LANGS = ('en', 'bs')


class LangContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        raw_lang = self.request.query_params.get('lang', 'en').lower()
        context['lang'] = raw_lang if raw_lang in _ALLOWED_LANGS else 'en'
        return context


class AlbumListView(LangContextMixin, generics.ListAPIView):
    serializer_class = AlbumListSerializer

    def get_queryset(self):
        return Album.objects.filter(is_published=True)


class AlbumDetailView(LangContextMixin, generics.RetrieveAPIView):
    serializer_class = AlbumDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Album.objects.filter(is_published=True)


class AlbumMediaListView(LangContextMixin, generics.ListAPIView):
    serializer_class = MediaItemPublicSerializer

    def get_queryset(self):
        album = generics.get_object_or_404(
            Album, slug=self.kwargs['slug'], is_published=True
        )
        return MediaItem.objects.filter(album=album, is_published=True)


class MediaItemDetailView(LangContextMixin, generics.RetrieveAPIView):
    serializer_class = MediaItemPublicSerializer

    def get_queryset(self):
        return MediaItem.objects.filter(
            is_published=True, album__is_published=True
        )


class FieldNoteListView(LangContextMixin, generics.ListAPIView):
    serializer_class = FieldNoteListSerializer

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)


class FieldNoteDetailView(LangContextMixin, generics.RetrieveAPIView):
    serializer_class = FieldNoteDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return FieldNote.objects.filter(is_published=True)

