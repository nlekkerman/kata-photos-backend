from django.urls import include, path

app_name = "admin_api"

urlpatterns = [
    path(
        "audit/",
        include("audit.urls", namespace="audit"),
    ),
]