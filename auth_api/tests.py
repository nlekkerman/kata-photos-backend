from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class SessionViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="staffpass", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regular", password="regularpass", is_staff=False
        )

    def test_anonymous_session_returns_unauthenticated(self):
        response = self.client.get(reverse("auth-session"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["is_authenticated"])
        self.assertFalse(data["is_staff"])
        self.assertEqual(data["username"], "")

    def test_staff_session_returns_authenticated_and_staff(self):
        self.client.login(username="staff", password="staffpass")
        response = self.client.get(reverse("auth-session"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_authenticated"])
        self.assertTrue(data["is_staff"])
        self.assertEqual(data["username"], "staff")

    def test_non_staff_session_returns_authenticated_not_staff(self):
        self.client.login(username="regular", password="regularpass")
        response = self.client.get(reverse("auth-session"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_authenticated"])
        self.assertFalse(data["is_staff"])
        self.assertEqual(data["username"], "regular")


class CsrfViewTests(TestCase):
    def test_csrf_endpoint_returns_200_with_token(self):
        response = self.client.get(reverse("auth-csrf"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("csrfToken", data)
        self.assertTrue(len(data["csrfToken"]) > 0)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="staffpass", is_staff=True
        )

    def test_logout_clears_session(self):
        self.client.login(username="staff", password="staffpass")
        # Confirm authenticated first
        session_resp = self.client.get(reverse("auth-session"))
        self.assertTrue(session_resp.json()["is_authenticated"])

        # Django test client enforces CSRF on POST; use enforce_csrf_checks=False (default)
        response = self.client.post(
            reverse("auth-logout"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"detail": "Logged out"})

        # Confirm anonymous after logout
        session_resp = self.client.get(reverse("auth-session"))
        self.assertFalse(session_resp.json()["is_authenticated"])


class LoginViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffuser", password="goodpass", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regularuser", password="goodpass", is_staff=False
        )

    def _post_login(self, body):
        return self.client.post(
            reverse("auth-login"),
            data=body,
            content_type="application/json",
        )

    def test_valid_staff_credentials_log_in(self):
        response = self._post_login(
            {"username": "staffuser", "password": "goodpass"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_authenticated"])
        self.assertTrue(data["is_staff"])
        self.assertEqual(data["username"], "staffuser")

    def test_invalid_credentials_return_400(self):
        response = self._post_login(
            {"username": "staffuser", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_non_staff_user_cannot_log_in_via_api(self):
        response = self._post_login(
            {"username": "regularuser", "password": "goodpass"}
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_credentials_return_400(self):
        response = self._post_login({"username": "staffuser"})
        self.assertEqual(response.status_code, 400)
