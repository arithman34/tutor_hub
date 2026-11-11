from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from billing.models import Payee, Payment


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class PaymentsListPageTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Sam", last_name="Smith")

    def test_owner_sees_payments(self):
        Payment.objects.create(user=self.admin, payee=self.payee, amount=100, payment_date=timezone.now())
        login(self.client, self.admin)
        response = self.client.get("/payments")
        self.assertContains(response, "Sam")
        self.assertContains(response, "100.00")

    def test_does_not_show_another_accounts_payments(self):
        Payment.objects.create(user=self.admin, payee=self.payee, amount=100, payment_date=timezone.now())
        login(self.client, make_user("tutor@example.com"))
        response = self.client.get("/payments")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Sam")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/payments")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_search_filters_by_payee_name(self):
        other = Payee.objects.create(user=self.admin, first_name="Pat", last_name="Jones")
        Payment.objects.create(user=self.admin, payee=self.payee, amount=100, payment_date=timezone.now())
        Payment.objects.create(user=self.admin, payee=other, amount=50, payment_date=timezone.now())
        login(self.client, self.admin)
        response = self.client.get("/payments", {"q": "Sam"})
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat")


class PaymentsNewPageTests(TestCase):
    def test_lists_only_own_payees(self):
        admin = make_user("admin@example.com")
        Payee.objects.create(user=admin, first_name="Sam", last_name="Smith")
        Payee.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones")
        login(self.client, admin)
        response = self.client.get("/payments/new")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat")


class PaymentCreateTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Sam", last_name="Smith")

    def _payload(self, **overrides):
        payload = {
            "payee_id": str(self.payee.id),
            "amount": "100.00",
            "payment_date": "2026-06-15",
            "payment_reference": "bank-ref",
        }
        payload.update(overrides)
        return payload

    def test_owner_can_create_payment(self):
        login(self.client, self.admin)
        response = self.client.post("/payments", self._payload())
        self.assertRedirects(response, "/payments", fetch_redirect_response=False)
        payment = Payment.objects.get()
        self.assertEqual(payment.payee_id, self.payee.id)
        self.assertEqual(str(payment.amount), "100.00")
        self.assertEqual(payment.payment_reference, "bank-ref")

    def test_cannot_record_payment_against_another_accounts_payee(self):
        login(self.client, make_user("tutor@example.com"))
        response = self.client.post("/payments", self._payload())
        self.assertRedirects(response, "/payments/new", fetch_redirect_response=False)
        self.assertEqual(Payment.objects.count(), 0)

    def test_invalid_payee_id_redirects_back(self):
        login(self.client, self.admin)
        response = self.client.post("/payments", self._payload(payee_id="not-a-uuid"))
        self.assertRedirects(response, "/payments/new", fetch_redirect_response=False)
        self.assertEqual(Payment.objects.count(), 0)


class PaymentFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.admin = make_user("admin@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Sam", last_name="Smith")
        login(self.client, self.admin)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    def test_create_form_includes_working_csrf_token(self):
        token = self._csrf_token("/payments/new")
        response = self.client.post(
            "/payments",
            {
                "payee_id": str(self.payee.id),
                "amount": "100.00",
                "payment_date": "2026-06-15",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)
