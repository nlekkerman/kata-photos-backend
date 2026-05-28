from django.contrib import admin

from .models import Album, MediaItem


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'display_order', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'slug')
    ordering = ('display_order', 'title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'album', 'media_type', 'provider', 'is_published', 'display_order')
    list_filter = ('is_published', 'media_type', 'provider')
    search_fields = ('title', 'alt_text', 'provider_public_id')
    ordering = ('album', 'display_order', 'id')
    readonly_fields = ('created_at', 'updated_at')

