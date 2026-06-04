from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class SessionView(APIView):
    """Return the current session's authentication state."""

    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        if user.is_authenticated:
            return Response(
                {
                    "is_authenticated": True,
                    "is_staff": user.is_staff,
                    "username": user.username,
                }
            )
        return Response(
            {
                "is_authenticated": False,
                "is_staff": False,
                "username": "",
            }
        )


class CsrfView(APIView):
    """Ensure the CSRF cookie is set so the frontend can read it."""

    permission_classes = [AllowAny]
    # GET is safe — no CSRF enforcement needed on the view itself.
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LogoutView(APIView):
    """Destroy the current session."""

    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out"})


class LoginView(APIView):
    """Authenticate with username/password and start a session.

    Only staff users may log in through this endpoint.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"detail": "username and password are required."}, status=400
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=400)

        if not user.is_staff:
            return Response({"detail": "Staff access required."}, status=403)

        login(request, user)
        return Response(
            {
                "is_authenticated": True,
                "is_staff": user.is_staff,
                "username": user.username,
            }
        )
