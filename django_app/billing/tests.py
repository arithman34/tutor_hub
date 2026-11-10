from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from students.models import Student
from tutoring_sessions.models import Session

from .models import Payee, Payment


def make_user(email, role=UserRole.TUTOR):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role)


class PayeeAccessTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Jo", last_name="Payer")
        self.list_url = reverse("payee-list")
        self.detail_url = reverse("payee-detail", args=[self.payee.id])

    def test_tutor_cannot_list_payees(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_payees(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_create_payee_with_capitalised_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {"first_name": "sam", "last_name": "jones"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "Sam")

    def test_tutor_cannot_create_payee(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.list_url, {"first_name": "sam", "last_name": "jones"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tutor_cannot_delete_payee(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_payee(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class PayeeBalanceTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Jo", last_name="Payer")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", payee=self.payee, hourly_rate=40)

        now = timezone.now()
        Session.objects.create(
            user=self.tutor,
            student=self.student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
        )
        Payment.objects.create(user=self.admin, payee=self.payee, amount=Decimal("100.00"), payment_date=now)

        self.balance_url = reverse("payee-balance", args=[self.payee.id])

    def test_balance_is_payments_minus_session_cost(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 100 paid - (1 hour * £40/hr) = 60
        self.assertEqual(response.data["balance"], 60.0)

    def test_tutor_cannot_view_balance(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PaymentAccessTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Jo", last_name="Payer")
        self.list_url = reverse("payment-list")

    def test_admin_can_create_payment(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            {"payee": str(self.payee.id), "amount": "50.00", "payment_date": timezone.now().isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.get().user, self.admin)

    def test_tutor_cannot_list_payments(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
