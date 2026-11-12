from django.test import Client, TestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import User


class HomePageTests(TestCase):
    def test_shows_landing_page_when_signed_out(self):
        response = self.client.get("/")
        self.assertContains(response, "Run a tutoring business from one place.")
        self.assertContains(response, 'href="/app/login"')
        self.assertContains(response, 'href="/privacy"')

    def test_sends_a_signed_in_user_to_the_app(self):
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B")
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        response = self.client.get("/")
        self.assertRedirects(response, "/app/", fetch_redirect_response=False)

    def test_a_refresh_token_alone_counts_as_signed_in_without_rotating_it(self):
        # The app refreshes the access token itself on its first API call.
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B")
        self.client.cookies["refresh_token"] = str(RefreshToken.for_user(user))
        response = self.client.get("/")
        self.assertRedirects(response, "/app/", fetch_redirect_response=False)
        self.assertNotIn("refresh_token", response.cookies)

    def test_a_blacklisted_refresh_token_shows_landing_page(self):
        user = User.objects.create_user(email="tutor@example.com", password="x", first_name="A", last_name="B")
        refresh = RefreshToken.for_user(user)
        refresh.blacklist()
        self.client.cookies["refresh_token"] = str(refresh)
        self.assertContains(self.client.get("/"), "Run a tutoring business from one place.")

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

    def test_public_layout_links_to_privacy(self):
        self.assertContains(self.client.get("/privacy"), 'href="/privacy"')


class GoogleScopeTests(TestCase):
    def test_requests_only_the_calendar_scope_the_privacy_policy_describes(self):
        from calendar_integration.services import _SCOPE

        self.assertEqual(_SCOPE.split(), ["https://www.googleapis.com/auth/calendar.app.created"])


class DemoSignInTests(TestCase):
    def test_homepage_offers_the_demo(self):
        response = self.client.get("/")
        self.assertContains(response, 'action="/demo"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    @override_settings(DEMO_ENABLED=False)
    def test_homepage_hides_the_demo_when_switched_off(self):
        self.assertNotContains(self.client.get("/"), 'action="/demo"')

    def test_signs_in_to_the_demo_and_opens_the_app(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/")
        response = client.post("/demo", {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})

        self.assertRedirects(response, "/app/", fetch_redirect_response=False)
        user = User.objects.get(email="demo@tutorhub.test")
        self.assertTrue(user.is_demo)
        access = AccessToken(response.cookies["access_token"].value)
        self.assertEqual(access["user_id"], str(user.id))
        self.assertTrue(response.cookies["access_token"]["httponly"])

    def test_needs_the_csrf_token(self):
        # Otherwise another site could sign a visitor into the demo without them knowing.
        client = Client(enforce_csrf_checks=True)
        response = client.post("/demo")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_only_accepts_post(self):
        self.assertEqual(self.client.get("/demo").status_code, 405)

    @override_settings(DEMO_ENABLED=False)
    def test_says_so_when_the_demo_is_off(self):
        response = self.client.post("/demo")
        self.assertContains(response, "The demo isn't available right now.", status_code=503)
        self.assertNotIn("access_token", response.cookies)
