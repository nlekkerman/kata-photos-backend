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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title']

    def __str__(self):
        return self.title


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
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='local')
    provider_public_id = models.CharField(max_length=500, blank=True)
    original_file = models.FileField(upload_to='media/originals/', null=True, blank=True)
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
        return self.title or f'MediaItem {self.pk}'

