from django.core.exceptions import ValidationError
from django.db import models


class Album(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title_en', 'title']

    def __str__(self):
        return self.title_en or self.title or f'Album {self.pk}'


class MediaItem(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    PROVIDER_CHOICES = [
        ('local', 'Local'),
        ('cloudinary', 'Cloudinary'),
        ('cloudflare_stream', 'Cloudflare Stream'),
    ]

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='media_items')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image')
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    alt_text = models.CharField(max_length=500, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True)
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
    original_file = models.FileField(upload_to='gallery/originals/', null=True, blank=True)
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
        return self.title_en or self.title or f'MediaItem {self.pk}'


class FieldNote(models.Model):
    slug = models.SlugField(max_length=200, unique=True)

    title_en = models.CharField(max_length=200)
    title_bs = models.CharField(max_length=200, blank=True)

    excerpt_en = models.TextField(blank=True)
    excerpt_bs = models.TextField(blank=True)

    body_en = models.TextField()
    body_bs = models.TextField(blank=True)

    location = models.CharField(max_length=200, blank=True)

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

    def clean(self):
        if self.is_published:
            errors = {}
            if not self.title_en:
                errors['title_en'] = 'Title (English) is required before publishing.'
            if not self.body_en:
                errors['body_en'] = 'Body (English) is required before publishing.'
            if errors:
                raise ValidationError(errors)

    def __str__(self):
        return self.title_en or f'FieldNote {self.pk}'

