"""The dashboard endpoint, and that the analytics responses match their documented shapes."""

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student

from .serializers import DashboardSerializer, FilterOptionsSerializer, TrendsSerializer


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class DashboardApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_returns_own_headline_numbers(self):
        Student.objects.create(user=self.user, first_name="Mine", last_name="One", is_active=True)
        payee = Payee.objects.create(user=self.user, first_name="P", last_name="Q")
        Payment.objects.create(user=self.user, payee=payee, amount=40, payment_date="2026-01-05T10:00:00Z")
        other = make_user("other@example.com")
        Student.objects.create(user=other, first_name="Theirs", last_name="Two", is_active=True)

        response = self.client.get("/api/v1/analytics/dashboard")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()), set(DashboardSerializer().fields))
        self.assertEqual(response.json()["active_students"], 1)
        self.assertEqual(response.json()["revenue_alltime"], 40.0)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get("/api/v1/analytics/dashboard").status_code, status.HTTP_401_UNAUTHORIZED)


class DocumentedShapeTests(APITestCase):
    """The schema is generated from these serializers, so the real responses must match them."""

    def setUp(self):
        self.client.force_authenticate(make_user())

    def assert_matches(self, serializer_class, data):
        serializer = serializer_class(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_trends_response(self):
        response = self.client.get("/api/v1/analytics/trends", {"range": "3m"})
        self.assert_matches(TrendsSerializer, response.json())

    def test_filter_options_response(self):
        self.assert_matches(FilterOptionsSerializer, self.client.get("/api/v1/analytics/filters").json())
