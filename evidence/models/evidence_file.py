import uuid

from django.db import models
from django.db.models import Q


class EvidenceFile(models.Model):
    """
    File/media reference for an EvidenceItem.

    This model does not need to upload files yet. For MVP admin smoke testing,
    it stores references to where files live or will live later.

    MVP scope:
    - Store file metadata.
    - Support external storage providers such as Cloudinary, Cloudflare Stream,
      S3-compatible storage, or local/manual archive references.

    Left for later:
    - Real file ingestion service.
    - Duplicate detection by checksum.
    - Media processing status.
    - Safe public derivatives and redacted versions.
    """

    class FileType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        DOCUMENT = "document", "Document"
        METADATA = "metadata", "Metadata"
        OTHER = "other", "Other"

    class StorageProvider(models.TextChoices):
        CLOUDINARY = "cloudinary", "Cloudinary"
        CLOUDFLARE_STREAM = "cloudflare_stream", "Cloudflare Stream"
        S3 = "s3", "S3-compatible storage"
        LOCAL_ARCHIVE = "local_archive", "Local archive"
        EXTERNAL_URL = "external_url", "External URL"
        MANUAL_REFERENCE = "manual_reference", "Manual reference"
        OTHER = "other", "Other"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    evidence_item = models.ForeignKey(
        "evidence.EvidenceItem",
        on_delete=models.CASCADE,
        related_name="files",
    )

    file_type = models.CharField(
        max_length=40,
        choices=FileType.choices,
        default=FileType.VIDEO,
    )

    storage_provider = models.CharField(
        max_length=60,
        choices=StorageProvider.choices,
        default=StorageProvider.MANUAL_REFERENCE,
    )

    original_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename if known.",
    )

    storage_key = models.CharField(
        max_length=500,
        blank=True,
        help_text="Provider-specific storage key, public ID, UID, object key, or archive reference.",
    )

    external_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="Optional external URL when file is referenced by URL.",
    )

    mime_type = models.CharField(max_length=120, blank=True)

    file_size_bytes = models.PositiveBigIntegerField(
        blank=True,
        null=True,
        help_text="File size in bytes if known.",
    )

    checksum = models.CharField(
        max_length=128,
        blank=True,
        help_text="Optional checksum for future duplicate/integrity validation.",
    )

    duration_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Duration for video/audio evidence files.",
    )

    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)

    is_primary = models.BooleanField(
        default=False,
        help_text="Marks the main file/preview for this evidence item.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "created_at"]
        verbose_name = "Evidence file"
        verbose_name_plural = "Evidence files"
        indexes = [
            models.Index(fields=["evidence_item", "file_type"]),
            models.Index(fields=["storage_provider"]),
            models.Index(fields=["checksum"]),
            models.Index(fields=["is_primary"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["evidence_item"],
                condition=Q(is_primary=True),
                name="unique_primary_file_per_evidence_item",
            ),
        ]

    def __str__(self):
        label = self.original_filename or self.storage_key or self.external_url or "Unnamed file"
        return f"{self.evidence_item.code} - {label}"