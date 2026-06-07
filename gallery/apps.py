from django.apps import AppConfig


class GalleryConfig(AppConfig):
    name = 'gallery'

    def ready(self):
        import gallery.signals  # noqa: F401 — registers post_save signal handlers
