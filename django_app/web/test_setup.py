from django.test import Client, TestCase

from accounts.models import User, UserRole


class SetupPageTests(TestCase):
    def test_shows_form_when_no_users_exist(self):
        response = self.client.get("/setup")
        self.assertContains(response, "Create your admin account")

    def test_redirects_to_login_when_users_already_exist(self):
        User.objects.create_user(email="existing@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN)
        response = self.client.get("/setup")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)


class SetupSubmitTests(TestCase):
    def test_creates_first_admin_and_redirects_to_login(self):
        response = self.client.post(
            "/setup",
            {"first_name": "jane", "last_name": "doe", "email": "jane@example.com", "password": "secret123"},
        )
        self.assertRedirects(response, "/login", fetch_redirect_response=False)
        admin = User.objects.get(email="jane@example.com")
        self.assertEqual(admin.first_name, "Jane")
        self.assertEqual(admin.role, UserRole.ADMIN)
        self.assertTrue(admin.check_password("secret123"))

    def test_rejected_when_users_already_exist(self):
        User.objects.create_user(email="existing@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN)
        response = self.client.post(
            "/setup",
            {"first_name": "jane", "last_name": "doe", "email": "jane@example.com", "password": "secret123"},
        )
        self.assertRedirects(response, "/login", fetch_redirect_response=False)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.filter(email="jane@example.com").exists())


class SetupFormCsrfTests(TestCase):
    def test_form_includes_working_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/setup")
        token = client.cookies["csrftoken"].value
        response = client.post(
            "/setup",
            {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com", "password": "secret123", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)
