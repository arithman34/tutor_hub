from django.test import TestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class HomePageTests(TestCase):
    def test_shows_landing_page_when_signed_out(self):
        response = self.client.get("/")
        self.assertContains(response, "Run a tutoring business from one place.")
        self.assertContains(response, 'href="/login"')
        self.assertContains(response, 'href="/privacy"')

    def test_redirects_signed_in_user_to_dashboard(self):
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B")
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        response = self.client.get("/")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)

    def test_refreshes_expired_access_token_on_redirect(self):
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B")
        self.client.cookies["refresh_token"] = str(RefreshToken.for_user(user))
        response = self.client.get("/")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_invalid_token_shows_landing_page(self):
        self.client.cookies["access_token"] = "not-a-token"
        response = self.client.get("/")
        self.assertContains(response, "Run a tutoring business from one place.")

    def test_inactive_user_shows_landing_page(self):
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B", is_active=False)
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        response = self.client.get("/")
        self.assertContains(response, "Run a tutoring business from one place.")

    def test_rejects_post(self):
        self.assertEqual(self.client.post("/").status_code, 405)


class PrivacyPageTests(TestCase):
    def test_is_public(self):
        response = self.client.get("/privacy")
        self.assertContains(response, "<h1 class=\"th-page-title\">Privacy policy</h1>", html=False)

    def test_describes_google_scopes_and_limited_use(self):
        response = self.client.get("/privacy")
        self.assertContains(response, "calendar.app.created")
        self.assertNotContains(response, "drive.file")
        self.assertContains(response, "https://developers.google.com/terms/api-services-user-data-policy")
        self.assertContains(response, "Limited Use")

    @override_settings(CONTACT_EMAIL="")
    def test_falls_back_to_github_contact(self):
        response = self.client.get("/privacy")
        self.assertContains(response, "https://github.com/arithman34")
        self.assertNotContains(response, "mailto:")

    @override_settings(CONTACT_EMAIL="privacy@example.com")
    def test_shows_contact_email_when_configured(self):
        response = self.client.get("/privacy")
        self.assertContains(response, 'href="mailto:privacy@example.com"')

    def test_login_page_links_to_privacy(self):
        self.assertContains(self.client.get("/login"), 'href="/privacy"')


class GoogleScopeTests(TestCase):
    def test_requests_only_the_calendar_scope_the_privacy_policy_describes(self):
        from calendar_integration.services import _SCOPE

        self.assertEqual(_SCOPE.split(), ["https://www.googleapis.com/auth/calendar.app.created"])
