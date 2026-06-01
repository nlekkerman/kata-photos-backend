from django.urls import path

from .views import CsrfView, LoginView, LogoutView, SessionView

urlpatterns = [
    path("session/", SessionView.as_view(), name="auth-session"),
    path("csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("login/", LoginView.as_view(), name="auth-login"),
]
