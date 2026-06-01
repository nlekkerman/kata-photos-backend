from django.contrib import admin

from .models import Album, FieldNote, MediaItem, VideoClip


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title_bs', 'slug', 'is_published', 'display_order', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title_bs', 'title_en', 'slug')
    ordering = ('display_order', 'title_bs')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('title_bs',)}
    fieldsets = (
        ('Publishing / Ordering', {
            'fields': ('slug', 'is_published', 'display_order', 'cover_media'),
        }),
        ('Bosnian Content', {
            'fields': ('title_bs', 'description_bs'),
        }),
        ('English Content', {
            'fields': ('title_en', 'description_en'),
        }),
        ('SEO Bosnian', {
            'fields': ('seo_title_bs', 'seo_description_bs'),
        }),
        ('SEO English', {
            'fields': ('seo_title_en', 'seo_description_en'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_en', 'album', 'media_type', 'provider', 'is_published', 'display_order')
    list_filter = ('is_published', 'media_type', 'provider')
    search_fields = ('title_en', 'alt_text_en', 'provider_public_id')
    ordering = ('album', 'display_order', 'id')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Album / Publishing / Ordering', {
            'fields': ('album', 'media_type', 'is_published', 'display_order', 'tags'),
        }),
        ('English Content', {
            'fields': ('title_en', 'description_en', 'alt_text_en', 'caption_en'),
        }),
        ('Bosnian Content', {
            'fields': ('title_bs', 'description_bs', 'alt_text_bs', 'caption_bs'),
        }),
        ('Media / Provider', {
            'fields': ('provider', 'provider_public_id', 'original_file', 'public_url', 'thumbnail_url'),
        }),
        ('Metadata', {
            'fields': ('width', 'height', 'duration_seconds', 'file_size'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(FieldNote)
class FieldNoteAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'slug', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title_en', 'slug', 'location')
    ordering = ('-published_at', '-created_at')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('title_en',)}
    fieldsets = (
        ('Publishing', {
            'fields': ('slug', 'is_published', 'published_at', 'cover_image'),
        }),
        ('English Content', {
            'fields': ('title_en', 'excerpt_en', 'body_en'),
        }),
        ('Bosnian Content', {
            'fields': ('title_bs', 'excerpt_bs', 'body_bs'),
        }),
        ('Location', {
            'fields': ('location',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(VideoClip)
class VideoClipAdmin(admin.ModelAdmin):
    list_display = ('title_bs', 'album', 'cloudflare_uid', 'status', 'is_public', 'created_at')
    list_filter = ('status', 'is_public')
    search_fields = ('title_bs', 'title_en', 'cloudflare_uid')
    ordering = ('-created_at',)
    readonly_fields = ('cloudflare_uid', 'created_at', 'updated_at')
    fieldsets = (
        ('Album / Publishing', {
            'fields': ('album', 'status', 'is_public'),
        }),
        ('Bosnian Content', {
            'fields': ('title_bs', 'description_bs'),
        }),
        ('English Content', {
            'fields': ('title_en', 'description_en'),
        }),
        ('Cloudflare Stream', {
            'fields': ('cloudflare_uid', 'cloudflare_thumbnail_url', 'cloudflare_playback_url', 'duration_seconds'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
