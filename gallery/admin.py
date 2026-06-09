from django.contrib import admin

from .models import Album, AnalyticsEvent, FieldNote, MediaItem, Tag, VideoClip, VideoTimestampComment, VisitorMessage, VisitorMessageReply


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'page_path', 'video', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('page_path', 'video__title_bs', 'video__title_en')
    readonly_fields = ('event_type', 'page_path', 'video', 'album', 'created_at')
    ordering = ('-created_at',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name_bs', 'name_en', 'slug', 'created_at')
    search_fields = ('name_bs', 'name_en', 'slug')
    ordering = ('slug',)
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name_bs',)}


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title_bs', 'slug', 'gallery_type', 'is_published', 'display_order', 'created_at')
    list_filter = ('is_published', 'gallery_type')
    search_fields = ('title_bs', 'title_en', 'slug')
    ordering = ('gallery_type', 'display_order', 'title_bs')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('title_bs',)}
    filter_horizontal = ('tags',)
    fieldsets = (
        ('Publishing / Ordering', {
            'fields': ('slug', 'gallery_type', 'is_published', 'display_order', 'cover_media'),
        }),
        ('Tags', {
            'fields': ('tags',),
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
    filter_horizontal = ('tags',)
    fieldsets = (
        ('Album / Publishing', {
            'fields': ('album', 'status', 'is_public'),
        }),
        ('Tags', {
            'fields': ('tags',),
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


@admin.register(VisitorMessage)
class VisitorMessageAdmin(admin.ModelAdmin):
    list_display = ('sender_name', 'sender_email', 'subject', 'message_preview', 'video', 'timestamp_seconds', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender_name', 'sender_email', 'subject', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('replied_at', 'created_at', 'updated_at')
    actions = ['mark_read', 'mark_replied', 'archive_messages']
    fieldsets = (
        ('Sender', {
            'fields': ('sender_name', 'sender_email'),
        }),
        ('Message', {
            'fields': ('subject', 'message'),
        }),
        ('Video Context', {
            'fields': ('video', 'timestamp_seconds'),
        }),
        ('Status', {
            'fields': ('status',),
        }),
        ('Reply', {
            'fields': ('replied_at',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Preview')
    def message_preview(self, obj):
        if len(obj.message) > 50:
            return obj.message[:50] + '...'
        return obj.message

    @admin.action(description='Mark selected messages as read')
    def mark_read(self, request, queryset):
        updated = queryset.update(status=VisitorMessage.STATUS_READ)
        self.message_user(request, f'{updated} message(s) marked as read.')

    @admin.action(description='Mark selected messages as replied')
    def mark_replied(self, request, queryset):
        updated = queryset.update(status=VisitorMessage.STATUS_REPLIED)
        self.message_user(request, f'{updated} message(s) marked as replied.')

    @admin.action(description='Archive selected messages')
    def archive_messages(self, request, queryset):
        updated = queryset.update(status=VisitorMessage.STATUS_ARCHIVED)
        self.message_user(request, f'{updated} message(s) archived.')


@admin.register(VisitorMessageReply)
class VisitorMessageReplyAdmin(admin.ModelAdmin):
    list_display = ('visitor_message', 'reply_subject', 'sent_by', 'sent_at')
    list_filter = ('sent_at',)
    search_fields = ('reply_subject', 'reply_body', 'visitor_message__sender_name', 'visitor_message__sender_email')
    ordering = ('-sent_at',)
    readonly_fields = ('visitor_message', 'reply_subject', 'reply_body', 'sent_by', 'sent_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(VideoTimestampComment)
class VideoTimestampCommentAdmin(admin.ModelAdmin):
    list_display = ('video', 'author_name', 'text_preview', 'timestamp_seconds', 'status', 'created_at')
    list_editable = ('status',)
    list_filter = ('status', 'video', 'created_at')
    search_fields = ('author_name', 'author_email', 'text')
    ordering = ('-created_at',)
    readonly_fields = ('author_email', 'created_at', 'updated_at')
    actions = ['approve_comments', 'reject_comments', 'mark_pending']
    fieldsets = (
        ('Comment', {
            'fields': ('video', 'timestamp_seconds', 'author_name', 'author_email', 'text'),
        }),
        ('Moderation', {
            'fields': ('status',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Preview')
    def text_preview(self, obj):
        if len(obj.text) > 50:
            return obj.text[:50] + '...'
        return obj.text

    @admin.action(description='Approve selected comments')
    def approve_comments(self, request, queryset):
        updated = queryset.update(status=VideoTimestampComment.STATUS_APPROVED)
        self.message_user(request, f'{updated} comment(s) approved.')

    @admin.action(description='Reject selected comments')
    def reject_comments(self, request, queryset):
        updated = queryset.update(status=VideoTimestampComment.STATUS_REJECTED)
        self.message_user(request, f'{updated} comment(s) rejected.')

    @admin.action(description='Mark selected comments as pending')
    def mark_pending(self, request, queryset):
        updated = queryset.update(status=VideoTimestampComment.STATUS_PENDING)
        self.message_user(request, f'{updated} comment(s) marked as pending.')
