from django.urls import path

app_name = "audit"

urlpatterns = [
    # Audit exposes no public/admin API endpoints yet.
    # Audit records are currently available only through Django admin.
    #
    # Future canonical API route, if needed:
    # /api/admin/audit/
    #
    # Do not add:
    # /api/audit/
    #
    # Audit is sensitive platform history, not a standalone public API.
]