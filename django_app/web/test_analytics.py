from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from students.models import Student


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class AnalyticsPageTests(TestCase):
    def test_admin_sees_page(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/analytics")
        self.assertContains(response, "Analytics")

    def test_tutor_redirected_to_dashboard(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/analytics")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/analytics")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_filter_options_include_tutors_and_students(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        login(self.client, admin)
        response = self.client.get("/analytics")
        self.assertContains(response, "Sam Smith")


class AnalyticsDataTests(TestCase):
    def test_returns_json_with_default_range(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/analytics/data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["range"], "12m")
        self.assertIn("charts", data)
        self.assertIn("labels", data)

    def test_tutor_cannot_access(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/analytics/data")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)

    def test_invalid_tutor_id_is_ignored_rather_than_erroring(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/analytics/data", {"tutor_id": "not-a-uuid"})
        self.assertEqual(response.status_code, 200)

    def test_custom_range_is_honored(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/analytics/data", {"start": "2026-01-01", "end": "2026-01-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["range"], "custom")
