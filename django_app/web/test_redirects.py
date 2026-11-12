from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from calendar_integration import services


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class MovedPageTests(TestCase):
    """Bookmarks to the old server-rendered pages land on the React app."""

    def test_each_old_page_goes_to_its_react_page(self):
        cases = {
            "/login": "/app/login",
            "/dashboard": "/app/",
            "/students": "/app/students",
            "/students/new": "/app/students/new",
            "/students/1b0c6c1e-2f3a-4b5c-8d9e-0f1a2b3c4d5e": "/app/students/1b0c6c1e-2f3a-4b5c-8d9e-0f1a2b3c4d5e",
            "/sessions": "/app/sessions",
            "/calendar": "/app/sessions",
            "/calendar/create": "/app/sessions/schedule",
            "/calendar/connect": "/app/connections",
            "/payees/new": "/app/payees/new",
            "/payments": "/app/payments",
            "/assistant": "/app/assistant",
            "/analytics": "/app/analytics",
            "/connections": "/app/connections",
            "/profile": "/app/profile",
            "/data": "/app/data",
            "/setup": "/app/setup",
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                self.assertRedirects(self.client.get(old), new, fetch_redirect_response=False)

    def test_keeps_the_query_string(self):
        response = self.client.get("/sessions", {"status": "unlogged"})
        self.assertRedirects(response, "/app/sessions?status=unlogged", fetch_redirect_response=False)

    def test_is_temporary_and_only_for_reading(self):
        self.assertEqual(self.client.get("/students").status_code, 302)
        # The old forms posted to these; there's nothing to redirect a POST to.
        self.assertEqual(self.client.post("/students/new").status_code, 405)

    def test_only_old_page_paths_are_caught(self):
        self.assertEqual(self.client.get("/studentsfoo").status_code, 404)
        self.assertEqual(self.client.get("/logout").status_code, 404)


class GoogleCallbackTests(TestCase):
    """/calendar/callback is the redirect URI registered with Google. It's the
    API's callback, and it sends the browser on to the React Connections page."""

    def test_access_denied_redirects_with_error(self):
        response = self.client.get("/calendar/callback", {"error": "access_denied"})
        self.assertRedirects(response, "/app/connections?error=access_denied", fetch_redirect_response=False)

    def test_forged_state_redirects_with_invalid_state_error(self):
        response = self.client.get("/calendar/callback", {"state": "forged", "code": "abc"})
        self.assertRedirects(response, "/app/connections?error=invalid_state", fetch_redirect_response=False)

    @patch("calendar_integration.services.exchange_code", side_effect=RuntimeError("boom"))
    def test_exchange_failure_redirects_with_error(self, _mock_exchange):
        state = services.sign_connect_state(make_user("tutor@example.com"))
        with self.assertLogs("calendar_integration.views", "ERROR"):
            response = self.client.get("/calendar/callback", {"state": state, "code": "abc"})
        self.assertRedirects(response, "/app/connections?error=token_exchange_failed", fetch_redirect_response=False)

    @patch("calendar_integration.services.exchange_code")
    def test_successful_exchange_connects_the_user_named_in_the_state(self, mock_exchange):
        tutor = make_user("tutor@example.com")
        response = self.client.get("/calendar/callback", {"state": services.sign_connect_state(tutor), "code": "abc"})
        self.assertRedirects(response, "/app/connections?connected=1", fetch_redirect_response=False)
        mock_exchange.assert_called_once_with("abc", tutor)
