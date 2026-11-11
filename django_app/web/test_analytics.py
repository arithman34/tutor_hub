from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from students.models import Student


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class AnalyticsPageTests(TestCase):
    def test_any_account_sees_page(self):
        admin = make_user("admin@example.com")
        login(self.client, admin)
        response = self.client.get("/analytics")
        self.assertContains(response, "Analytics")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/analytics")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_filter_options_list_only_own_students(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones")
        login(self.client, tutor)
        response = self.client.get("/analytics")
        self.assertContains(response, "Sam Smith")
        self.assertNotContains(response, "Pat Jones")
        self.assertNotContains(response, "tutor_id")


class AnalyticsDataTests(TestCase):
    def test_returns_json_with_default_range(self):
        admin = make_user("admin@example.com")
        login(self.client, admin)
        response = self.client.get("/analytics/data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["range"], "12m")
        self.assertIn("charts", data)
        self.assertIn("labels", data)

    def test_invalid_student_id_is_ignored_rather_than_erroring(self):
        admin = make_user("admin@example.com")
        login(self.client, admin)
        response = self.client.get("/analytics/data", {"student_id": "not-a-uuid"})
        self.assertEqual(response.status_code, 200)

    def test_only_counts_own_students(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        Student.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones")
        login(self.client, tutor)
        data = self.client.get("/analytics/data").json()
        totals = {s["key"]: s["total"] for c in data["charts"] for s in c["series"]}
        self.assertEqual(totals["students_roster"], 1.0)

    def test_custom_range_is_honored(self):
        admin = make_user("admin@example.com")
        login(self.client, admin)
        response = self.client.get("/analytics/data", {"start": "2026-01-01", "end": "2026-01-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["range"], "custom")
