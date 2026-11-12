from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from students.models import Student
from tutoring_sessions.models import Session

from .models import Payee, Payment
from .services import payee_balances


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class PayeeAccessTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other = make_user("other@example.com")
        self.payee = Payee.objects.create(user=self.owner, first_name="Jo", last_name="Payer")
        self.list_url = reverse("payee-list")
        self.detail_url = reverse("payee-detail", args=[self.payee.id])

    def test_owner_can_list_payees(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_other_account_sees_no_payees(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_create_payee_capitalises_name_and_sets_owner(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(self.list_url, {"first_name": "sam", "last_name": "jones"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "Sam")
        self.assertEqual(Payee.objects.get(id=response.data["id"]).user, self.other)

    def test_owner_can_delete_payee(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_account_cannot_retrieve_update_or_delete(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.detail_url, {"first_name": "X"}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Payee.objects.filter(id=self.payee.id, first_name="Jo").exists())


class PayeeBalanceTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.payee = Payee.objects.create(user=self.owner, first_name="Jo", last_name="Payer")
        self.student = Student.objects.create(user=self.owner, first_name="Sam", last_name="Smith", payee=self.payee, hourly_rate=40)

        now = timezone.now()
        Session.objects.create(
            user=self.owner,
            student=self.student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
        )
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("100.00"), payment_date=now)

        self.balance_url = reverse("payee-balance", args=[self.payee.id])

    def test_balance_is_payments_minus_session_cost(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 100 paid - (1 hour * £40/hr) = 60
        self.assertEqual(response.data["balance"], 60.0)

    def test_other_account_cannot_view_balance(self):
        self.client.force_authenticate(make_user("other@example.com"))
        response = self.client.get(self.balance_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PayeeBalancesServiceTests(APITestCase):
    def test_balances_for_several_payees(self):
        owner = make_user("owner@example.com")
        now = timezone.now()
        owing = Payee.objects.create(user=owner, first_name="Owe", last_name="Ing")
        in_credit = Payee.objects.create(user=owner, first_name="In", last_name="Credit")
        unbilled = Payee.objects.create(user=owner, first_name="No", last_name="Rate")

        billed_student = Student.objects.create(user=owner, first_name="A", last_name="A", payee=owing, hourly_rate=30)
        free_student = Student.objects.create(user=owner, first_name="B", last_name="B", payee=unbilled)
        for student in (billed_student, billed_student, free_student):
            Session.objects.create(
                user=owner,
                student=student,
                session_date=now,
                session_start_time=now,
                session_end_time=now + timedelta(minutes=90),
            )
        Payment.objects.create(user=owner, payee=in_credit, amount=Decimal("25.00"), payment_date=now)

        balances = payee_balances([owing, in_credit, unbilled])
        # 2 sessions * 1.5h * £30 = £90 owed
        self.assertEqual(balances, {owing.id: -90.0, in_credit.id: 25.0, unbilled.id: 0.0})

    def test_empty_input(self):
        self.assertEqual(payee_balances([]), {})


class PaymentAccessTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other = make_user("other@example.com")
        self.payee = Payee.objects.create(user=self.owner, first_name="Jo", last_name="Payer")
        self.list_url = reverse("payment-list")

    def _payload(self, payee):
        return {"payee": str(payee.id), "amount": "50.00", "payment_date": timezone.now().isoformat()}

    def test_owner_can_create_payment(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.list_url, self._payload(self.payee))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.get().user, self.owner)

    def test_cannot_record_payment_against_another_accounts_payee(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(self.list_url, self._payload(self.payee))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

    def test_list_only_shows_own_payments(self):
        Payment.objects.create(user=self.owner, payee=self.payee, amount=Decimal("10.00"), payment_date=timezone.now())
        self.client.force_authenticate(self.other)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
