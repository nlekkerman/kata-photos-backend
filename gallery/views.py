from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Album, FieldNote, MediaItem
from .serializers import (
    AlbumCoverWriteSerializer,
    AlbumDetailSerializer,
    AlbumListSerializer,
    AlbumWriteSerializer,
    FieldNoteDetailSerializer,
    FieldNoteListSerializer,
    MediaItemPublicSerializer,
    MediaItemWriteSerializer,
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
        serializer.save(album=album, provider='local')


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

