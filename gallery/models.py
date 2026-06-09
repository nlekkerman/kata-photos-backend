import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Tag(models.Model):
    CATEGORY_LOCATION = 'location'
    CATEGORY_SPECIES = 'species'
    CATEGORY_HABITAT = 'habitat'
    CATEGORY_BEHAVIOR = 'behavior'
    CATEGORY_CONTENT_TYPE = 'content_type'
    CATEGORY_GENERAL = 'general'

    CATEGORY_CHOICES = [
        (CATEGORY_LOCATION, 'Location'),
        (CATEGORY_SPECIES, 'Species'),
        (CATEGORY_HABITAT, 'Habitat'),
        (CATEGORY_BEHAVIOR, 'Behavior'),
        (CATEGORY_CONTENT_TYPE, 'Content Type'),
        (CATEGORY_GENERAL, 'General'),
    ]

    name_bs = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=120, unique=True)
    category = models.CharField(
        max_length=40,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL,
        db_index=True,
    )
    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slug']

    def __str__(self):
        return self.name_bs or self.name_en or self.slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_bs or self.name_en)
        super().save(*args, **kwargs)


class Album(models.Model):
    GALLERY_TYPE_IMAGE = 'image'
    GALLERY_TYPE_VIDEO = 'video'
    GALLERY_TYPE_CHOICES = [
        (GALLERY_TYPE_IMAGE, 'Image Gallery'),
        (GALLERY_TYPE_VIDEO, 'Video Gallery'),
    ]

    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True)
    gallery_type = models.CharField(
        max_length=10,
        choices=GALLERY_TYPE_CHOICES,
        default=GALLERY_TYPE_IMAGE,
    )
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    cover_media = models.ForeignKey(
        'MediaItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cover_for_albums',
    )
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    title_bs = models.CharField(max_length=200, blank=True)
    description_en = models.TextField(blank=True)
    description_bs = models.TextField(blank=True)
    seo_title_en = models.CharField(max_length=200, blank=True)
    seo_title_bs = models.CharField(max_length=200, blank=True)
    seo_description_en = models.TextField(blank=True)
    seo_description_bs = models.TextField(blank=True)
    tags = models.ManyToManyField('Tag', blank=True, related_name='albums')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title_en', 'title']

    def __str__(self):
        return self.title_bs or self.title_en or self.title or f'Album {self.pk}'

    def clean(self):
        if self.is_published and not self.title_bs:
            raise ValidationError({'title_bs': 'Naslov na bosanskom je obavezan za objavljene albume.'})


class MediaItem(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    PROVIDER_CHOICES = [
        ('local', 'Local'),
        ('cloudinary', 'Cloudinary'),
        ('cloudflare_images', 'Cloudflare Images'),
        ('cloudflare_stream', 'Cloudflare Stream'),
    ]

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='media_items')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image')
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    alt_text = models.CharField(max_length=500, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    tags = models.ManyToManyField('Tag', blank=True, related_name='media_items')
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    title_en = models.CharField(max_length=200, blank=True)
    title_bs = models.CharField(max_length=200, blank=True)
    description_en = models.TextField(blank=True)
    description_bs = models.TextField(blank=True)
    alt_text_en = models.CharField(max_length=500, blank=True)
    alt_text_bs = models.CharField(max_length=500, blank=True)
    caption_en = models.CharField(max_length=500, blank=True)
    caption_bs = models.CharField(max_length=500, blank=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='local')
    provider_public_id = models.CharField(max_length=500, blank=True)
    original_file = models.ImageField(upload_to='gallery/originals/', null=True, blank=True)
    public_url = models.URLField(max_length=1000, blank=True)
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.title_bs or self.title_en or self.title or f'MediaItem {self.pk}'

    def save(self, *args, **kwargs):
        if self.provider == 'local' and self.original_file:
            self._populate_local_image_metadata()
        super().save(*args, **kwargs)

    def _populate_local_image_metadata(self):
        """Populate width, height, file_size from original_file for local uploads."""
        from PIL import Image, UnidentifiedImageError

        f = self.original_file

        if not f._committed:
            # New upload — file not yet written to storage
            raw = f.file
            self.file_size = raw.size
            raw.seek(0)
            try:
                with Image.open(raw) as img:
                    self.width, self.height = img.size
            except (UnidentifiedImageError, Exception):
                pass
            raw.seek(0)
        else:
            # Existing committed file on disk — only fill missing fields
            if not (self.width and self.height and self.file_size):
                try:
                    path = f.path
                    if not self.file_size:
                        self.file_size = os.path.getsize(path)
                    if not (self.width and self.height):
                        with Image.open(path) as img:
                            self.width, self.height = img.size
                except (UnidentifiedImageError, Exception):
                    pass


class FieldNote(models.Model):
    slug = models.SlugField(max_length=200, unique=True, blank=True)

    title_bs = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200, blank=True)

    excerpt_bs = models.TextField(blank=True)
    excerpt_en = models.TextField(blank=True)

    body_bs = models.TextField()
    body_en = models.TextField(blank=True)

    location_bs = models.CharField(max_length=200, blank=True)
    location_en = models.CharField(max_length=200, blank=True)

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    cover_image = models.ForeignKey(
        'MediaItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cover_for_field_notes',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['is_published', '-published_at']),
            models.Index(fields=['slug']),
        ]

    def clean(self):
        errors = {}

        if self.is_published:
            if not self.title_bs:
                errors['title_bs'] = 'Title (Bosnian) is required before publishing.'
            if not self.body_bs:
                errors['body_bs'] = 'Body (Bosnian) is required before publishing.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()

        if not self.slug:
            base_slug = slugify(self.title_en or self.title_bs) or "field-note"
            slug = base_slug
            counter = 2

            while FieldNote.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title_bs or self.title_en or f'FieldNote {self.pk}'

class VideoClip(models.Model):
    STATUS_UPLOADING = 'uploading'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_UPLOADING, 'Uploading'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    TITLE_SOURCE_MANUAL = 'manual'
    TITLE_SOURCE_BACKEND_AUTO = 'backend_auto'
    TITLE_SOURCE_FILENAME = 'filename'
    TITLE_SOURCE_CLOUDFLARE = 'cloudflare'
    TITLE_SOURCE_UNKNOWN = 'unknown'

    TITLE_SOURCE_CHOICES = [
        (TITLE_SOURCE_MANUAL, 'Manual'),
        (TITLE_SOURCE_BACKEND_AUTO, 'Backend auto-generated'),
        (TITLE_SOURCE_FILENAME, 'Derived from filename'),
        (TITLE_SOURCE_CLOUDFLARE, 'Cloudflare metadata'),
        (TITLE_SOURCE_UNKNOWN, 'Unknown'),
    ]

    album = models.ForeignKey(
        'gallery.Album',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='videos',
    )
    title_bs = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    description_bs = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    cloudflare_uid = models.CharField(max_length=128, unique=True)
    cloudflare_thumbnail_url = models.URLField(blank=True)
    cloudflare_playback_url = models.URLField(blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UPLOADING)
    is_public = models.BooleanField(default=False)
    tags = models.ManyToManyField('Tag', blank=True, related_name='video_clips')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Upload audit fields
    original_filename = models.CharField(max_length=255, blank=True, default='')
    submitted_title_bs = models.CharField(max_length=255, blank=True, default='')
    title_source = models.CharField(
        max_length=20,
        choices=TITLE_SOURCE_CHOICES,
        default=TITLE_SOURCE_UNKNOWN,
    )

    # Cloudflare Stream status audit fields
    cloudflare_status_state = models.CharField(max_length=32, blank=True, default='')
    cloudflare_status_step = models.CharField(max_length=64, blank=True, default='')
    cloudflare_pct_complete = models.CharField(max_length=16, blank=True, default='')
    cloudflare_error_reason_code = models.CharField(max_length=64, blank=True, default='')
    cloudflare_error_reason_text = models.TextField(blank=True, default='')
    cloudflare_last_synced_at = models.DateTimeField(null=True, blank=True)

    # Processing tracking
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_warning = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['is_public', 'status', '-created_at', '-id'],
                name='video_pub_status_created_idx',
            ),
            models.Index(
                fields=['album', 'is_public', 'status', '-created_at', '-id'],
                name='video_album_public_created_idx',
            ),
        ]

    def __str__(self):
        return self.title_bs or self.title_en or f'VideoClip {self.pk}'


class VisitorMessage(models.Model):
    STATUS_NEW = 'new'
    STATUS_READ = 'read'
    STATUS_REPLIED = 'replied'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_READ, 'Read'),
        (STATUS_REPLIED, 'Replied'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    TRANSLATION_PENDING = 'pending'
    TRANSLATION_TRANSLATED = 'translated'
    TRANSLATION_SKIPPED = 'skipped'
    TRANSLATION_FAILED = 'failed'

    sender_name = models.CharField(max_length=120)
    sender_email = models.EmailField(max_length=254)
    subject = models.CharField(max_length=180)
    message = models.TextField()
    subject_bs = models.CharField(max_length=180, blank=True, default="")
    message_bs = models.TextField(blank=True, default="")
    translation_status = models.CharField(max_length=32, blank=True, default="")
    translation_error = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NEW)
    video = models.ForeignKey(
        'VideoClip',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visitor_messages',
    )
    timestamp_seconds = models.PositiveIntegerField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['sender_email']),
        ]

    def __str__(self):
        return f'{self.sender_name} — {self.subject}'


class VisitorMessageReply(models.Model):
    visitor_message = models.ForeignKey(
        'VisitorMessage',
        on_delete=models.CASCADE,
        related_name='replies',
    )
    reply_subject = models.CharField(max_length=250)
    reply_body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visitor_message_replies',
    )
    # Translation audit fields
    original_reply_body = models.TextField(blank=True, default='')
    sent_reply_body = models.TextField(blank=True, default='')
    visitor_language = models.CharField(max_length=16, blank=True, default='')
    reply_language = models.CharField(max_length=16, blank=True, default='')
    translation_applied = models.BooleanField(default=False)
    translation_skipped_reason = models.CharField(max_length=120, blank=True, default='')
    translation_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Visitor Message Reply'
        verbose_name_plural = 'Visitor Message Replies'

    def __str__(self):
        sender = self.sent_by.get_username() if self.sent_by_id else 'unknown'
        return f'Reply to #{self.visitor_message_id} by {sender}'


class VideoTimestampComment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    video = models.ForeignKey(
        'VideoClip',
        on_delete=models.CASCADE,
        related_name='timestamp_comments',
    )
    TRANSLATION_PENDING = 'pending'
    TRANSLATION_TRANSLATED = 'translated'
    TRANSLATION_SKIPPED = 'skipped'
    TRANSLATION_FAILED = 'failed'

    author_name = models.CharField(max_length=120)
    author_email = models.EmailField(max_length=254)
    text = models.TextField()
    text_bs = models.TextField(blank=True, default="")
    translation_status = models.CharField(max_length=32, blank=True, default="")
    translation_error = models.TextField(blank=True, default="")
    timestamp_seconds = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['timestamp_seconds', 'created_at']
        indexes = [
            models.Index(fields=['video', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.author_name} @ {self.timestamp_seconds}s — {self.video}'


class AnalyticsEvent(models.Model):
    """Anonymous first-party event record for admin KPI tracking.

    Privacy rules enforced at model level:
    - No IP address stored.
    - No user-agent stored.
    - No visitor identity or session stored.
    - Only aggregate-useful anonymous fields.
    """

    EVENT_PAGE_VIEW = 'page_view'
    EVENT_VIDEO_PLAY = 'video_play'

    EVENT_TYPE_CHOICES = [
        (EVENT_PAGE_VIEW, 'Page view'),
        (EVENT_VIDEO_PLAY, 'Video play'),
    ]

    event_type = models.CharField(max_length=40, choices=EVENT_TYPE_CHOICES)
    page_path = models.CharField(max_length=500, blank=True)
    video = models.ForeignKey(
        'VideoClip',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_events',
    )
    album = models.ForeignKey(
        'Album',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type'], name='analytics_event_type_idx'),
            models.Index(fields=['created_at'], name='analytics_created_at_idx'),
            models.Index(fields=['event_type', 'created_at'], name='analytics_type_created_idx'),
            models.Index(fields=['video', 'event_type'], name='analytics_video_type_idx'),
            models.Index(fields=['page_path', 'event_type'], name='analytics_path_type_idx'),
        ]

    def __str__(self):
        return f'{self.event_type} — {self.page_path or self.video_id} @ {self.created_at:%Y-%m-%d %H:%M}'


class AdminNotificationCheckpoint(models.Model):
    """One row per staff user; stores the last time each notification section was seen."""

    staff_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_checkpoint',
    )
    messages_seen_at = models.DateTimeField(null=True, blank=True)
    comments_seen_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admin Notification Checkpoint'
        verbose_name_plural = 'Admin Notification Checkpoints'

    def __str__(self):
        return f'Checkpoint for {self.staff_user}'

