from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # Existing legacy/auth routes — keep untouched for now.
    path("api/auth/", include("auth_api.urls")),
    path("api/gallery/", include("gallery.urls")),
    path("api/public/", include("gallery.public_urls")),
    path("share/", include("gallery.share_urls")),

    # New canonical Kata Wild API family routes.
    # Add new scientific/admin platform APIs here, not under random app routes.
    path("api/admin/", include("config.api_urls.admin_urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)