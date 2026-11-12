"""Balances, student counts, payee names and the ?payee= filters the React pages use."""

from datetime import datetime, timedelta, timezone

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from students.models import Student
from tutoring_sessions.models import Session

from .models import Payee, Payment


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


def lesson(user, student, hours=1):
    start = datetime(2026, 3, 5, 16, tzinfo=timezone.utc)
    return Session.objects.create(
        user=user, student=student, session_date=start, session_start_time=start, session_end_time=start + timedelta(hours=hours)
    )


class PayeeBalanceTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.pat = Payee.objects.create(user=self.user, first_name="Pat", last_name="Parent")
        sam = Student.objects.create(user=self.user, payee=self.pat, first_name="Sam", last_name="Smith", hourly_rate=30)
        Student.objects.create(user=self.user, payee=self.pat, first_name="Sue", last_name="Smith")
        lesson(self.user, sam, hours=2)
        Payment.objects.create(user=self.user, payee=self.pat, amount=40, payment_date=datetime(2026, 3, 6, tzinfo=timezone.utc))

    def test_list_includes_balance_and_student_count(self):
        response = self.client.get("/api/v1/payees/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [row] = response.json()
        # Paid £40, billed 2h x £30 = £60, so £20 owed.
        self.assertEqual(row["balance"], -20.0)
        self.assertEqual(row["student_count"], 2)

    def test_detail_includes_balance(self):
        response = self.client.get(f"/api/v1/payees/{self.pat.id}/")
        self.assertEqual(response.json()["balance"], -20.0)
        self.assertEqual(response.json()["student_count"], 2)

    def test_list_queries_dont_grow_with_payees(self):
        with CaptureQueriesContext(connection) as one_payee:
            self.client.get("/api/v1/payees/")
        for index in range(5):
            payee = Payee.objects.create(user=self.user, first_name=f"P{index}", last_name="X")
            Payment.objects.create(user=self.user, payee=payee, amount=5, payment_date=datetime(2026, 3, 6, tzinfo=timezone.utc))
        with self.assertNumQueries(len(one_payee.captured_queries)):
            response = self.client.get("/api/v1/payees/")
        self.assertEqual(len(response.json()), 6)

    def test_search_still_works(self):
        Payee.objects.create(user=self.user, first_name="Other", last_name="Person")
        self.assertEqual([p["first_name"] for p in self.client.get("/api/v1/payees/", {"q": "pat"}).json()], ["Pat"])

    def test_create_returns_zero_balance(self):
        response = self.client.post("/api/v1/payees/", {"first_name": "new", "last_name": "payee"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["balance"], 0.0)
        self.assertEqual(response.json()["student_count"], 0)


class PayeeFilterTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.pat = Payee.objects.create(user=self.user, first_name="Pat", last_name="Parent")
        self.lee = Payee.objects.create(user=self.user, first_name="Lee", last_name="Other")
        Student.objects.create(user=self.user, payee=self.pat, first_name="Sam", last_name="Smith")
        Student.objects.create(user=self.user, payee=self.lee, first_name="Alex", last_name="Jones")
        Student.objects.create(user=self.user, first_name="Solo", last_name="Student")
        for payee, amount in ((self.pat, 10), (self.pat, 20), (self.lee, 30)):
            Payment.objects.create(user=self.user, payee=payee, amount=amount, payment_date=datetime(2026, 3, 6, tzinfo=timezone.utc))

    def test_students_filtered_by_payee(self):
        response = self.client.get("/api/v1/students/", {"payee": str(self.pat.id)})
        self.assertEqual([s["first_name"] for s in response.json()], ["Sam"])

    def test_payments_filtered_by_payee(self):
        response = self.client.get("/api/v1/payments/", {"payee": str(self.pat.id)})
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual({p["payee_name"] for p in response.json()["results"]}, {"Pat Parent"})

    def test_invalid_ids_return_nothing(self):
        self.assertEqual(self.client.get("/api/v1/students/", {"payee": "nope"}).json(), [])
        self.assertEqual(self.client.get("/api/v1/payments/", {"payee": "nope"}).json()["count"], 0)

    def test_another_accounts_payee_returns_nothing(self):
        other = make_user("other@example.com")
        theirs = Payee.objects.create(user=other, first_name="T", last_name="S")
        Payment.objects.create(user=other, payee=theirs, amount=99, payment_date=datetime(2026, 3, 6, tzinfo=timezone.utc))
        self.assertEqual(self.client.get("/api/v1/payments/", {"payee": str(theirs.id)}).json()["count"], 0)

    def test_created_payment_includes_payee_name(self):
        response = self.client.post(
            "/api/v1/payments/",
            {"payee": str(self.lee.id), "amount": "12.50", "payment_date": "2026-03-07T00:00:00Z"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["payee_name"], "Lee Other")
        self.assertEqual(response.json()["amount"], "12.50")
