from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from calendar_integration.models import GoogleCalendarToken


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class ConnectionsPageTests(TestCase):
    def test_shows_not_connected_by_default(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/connections")
        self.assertContains(response, "Not connected")

    def test_shows_connected_when_token_has_refresh_token(self):
        tutor = make_user("tutor@example.com")
        GoogleCalendarToken.objects.create(user=tutor, access_token="x", refresh_token="y", expires_at=timezone.now())
        login(self.client, tutor)
        response = self.client.get("/connections")
        self.assertContains(response, "Connected")

    def test_disconnected_token_without_refresh_shows_not_connected(self):
        tutor = make_user("tutor@example.com")
        GoogleCalendarToken.objects.create(user=tutor, access_token="", refresh_token=None, expires_at=timezone.now())
        login(self.client, tutor)
        response = self.client.get("/connections")
        self.assertContains(response, "Not connected")

    def test_error_query_param_shows_message(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/connections", {"error": "not_connected"})
        self.assertContains(response, "Connect Google Calendar before creating sessions.")

    def test_connected_flash_shows_success_message(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/connections", {"connected": "1"})
        self.assertContains(response, "Google connected successfully.")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/connections")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)


class DisconnectTests(TestCase):
    def test_disconnect_clears_credentials_but_keeps_row(self):
        tutor = make_user("tutor@example.com")
        token = GoogleCalendarToken.objects.create(
            user=tutor, access_token="x", refresh_token="y", expires_at=timezone.now(), tutoring_calendar_id="cal-1"
        )
        login(self.client, tutor)
        response = self.client.post("/calendar/disconnect")
        self.assertRedirects(response, "/connections", fetch_redirect_response=False)
        token.refresh_from_db()
        self.assertEqual(token.access_token, "")
        self.assertIsNone(token.refresh_token)
        self.assertEqual(token.tutoring_calendar_id, "cal-1")


class ConnectTests(TestCase):
    @patch("calendar_integration.services.build_connect_url")
    def test_connect_redirects_to_google_and_sets_state_cookie(self, mock_build_url):
        mock_build_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?state=xyz"
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/calendar/connect")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://accounts.google.com/o/oauth2/v2/auth?state=xyz")
        self.assertIn("gcal_state", response.cookies)


class CallbackTests(TestCase):
    def test_access_denied_redirects_with_error(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/calendar/callback", {"error": "access_denied"})
        self.assertRedirects(response, "/connections?error=access_denied", fetch_redirect_response=False)

    def test_mismatched_state_redirects_with_invalid_state_error(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        self.client.cookies["gcal_state"] = "expected"
        response = self.client.get("/calendar/callback", {"state": "wrong", "code": "abc"})
        self.assertRedirects(response, "/connections?error=invalid_state", fetch_redirect_response=False)

    def test_missing_state_cookie_redirects_with_invalid_state_error(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/calendar/callback", {"state": "abc", "code": "abc"})
        self.assertRedirects(response, "/connections?error=invalid_state", fetch_redirect_response=False)

    @patch("calendar_integration.services.exchange_code", side_effect=RuntimeError("boom"))
    def test_exchange_failure_redirects_with_error(self, mock_exchange):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        self.client.cookies["gcal_state"] = "matching"
        response = self.client.get("/calendar/callback", {"state": "matching", "code": "abc"})
        self.assertRedirects(response, "/connections?error=token_exchange_failed", fetch_redirect_response=False)

    @patch("calendar_integration.services.exchange_code")
    def test_successful_exchange_redirects_with_connected_flag(self, mock_exchange):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        self.client.cookies["gcal_state"] = "matching"
        response = self.client.get("/calendar/callback", {"state": "matching", "code": "abc"})
        self.assertRedirects(response, "/connections?connected=1", fetch_redirect_response=False)
        mock_exchange.assert_called_once()


class DisconnectFormCsrfTests(TestCase):
    def test_disconnect_form_includes_working_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        tutor = make_user("tutor@example.com")
        GoogleCalendarToken.objects.create(user=tutor, access_token="x", refresh_token="y", expires_at=timezone.now())
        login(client, tutor)
        client.get("/connections")
        token = client.cookies["csrftoken"].value
        response = client.post("/calendar/disconnect", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
