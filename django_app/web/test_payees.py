from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class PayeesListPageTests(TestCase):
    def test_owner_sees_payees(self):
        admin = make_user("admin@example.com")
        Payee.objects.create(user=admin, first_name="Sam", last_name="Smith")
        login(self.client, admin)
        response = self.client.get("/payees")
        self.assertContains(response, "Sam")

    def test_does_not_show_another_accounts_payees(self):
        Payee.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones")
        login(self.client, make_user("tutor@example.com"))
        response = self.client.get("/payees")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Pat Jones")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/payees")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_search_filters_by_name(self):
        admin = make_user("admin@example.com")
        Payee.objects.create(user=admin, first_name="Sam", last_name="Smith")
        Payee.objects.create(user=admin, first_name="Pat", last_name="Jones")
        login(self.client, admin)
        response = self.client.get("/payees", {"q": "Sam"})
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat Jones")

    def test_balance_reflects_payments_minus_session_cost(self):
        admin = make_user("admin@example.com")
        payee = Payee.objects.create(user=admin, first_name="Sam", last_name="Smith")
        student = Student.objects.create(user=admin, payee=payee, first_name="Kid", last_name="One", hourly_rate=20.0)
        now = timezone.now()
        Session.objects.create(user=admin, student=student, session_date=now, session_start_time=now, session_end_time=now + timezone.timedelta(hours=1))
        Payment.objects.create(user=admin, payee=payee, amount=100, payment_date=now)
        login(self.client, admin)
        response = self.client.get("/payees")
        # paid 100 - cost (1hr * 20) = 80
        self.assertContains(response, "80.00")


class PayeesNewPageTests(TestCase):
    def test_renders_form(self):
        login(self.client, make_user("tutor@example.com"))
        response = self.client.get("/payees/new")
        self.assertEqual(response.status_code, 200)


class PayeeCreateTests(TestCase):
    def test_creates_payee_owned_by_current_user(self):
        admin = make_user("admin@example.com")
        login(self.client, admin)
        response = self.client.post(
            "/payees",
            {"first_name": "sam", "last_name": "smith", "email": "sam@example.com"},
        )
        self.assertRedirects(response, "/payees", fetch_redirect_response=False)
        payee = Payee.objects.get()
        self.assertEqual(payee.first_name, "Sam")
        self.assertEqual(payee.last_name, "Smith")
        self.assertEqual(payee.email, "sam@example.com")
        self.assertEqual(payee.user, admin)


class PayeeDetailAndUpdateTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com")
        self.tutor = make_user("tutor@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Sam", last_name="Smith")

    def test_owner_can_view(self):
        login(self.client, self.admin)
        response = self.client.get(f"/payees/{self.payee.id}")
        self.assertContains(response, "Sam")

    def test_other_account_redirected_to_list(self):
        login(self.client, self.tutor)
        response = self.client.get(f"/payees/{self.payee.id}")
        self.assertRedirects(response, "/payees", fetch_redirect_response=False)

    def test_other_account_cannot_update(self):
        login(self.client, self.tutor)
        response = self.client.post(f"/payees/{self.payee.id}/update", {"first_name": "hacked", "last_name": "x"})
        self.assertEqual(response.status_code, 404)
        self.payee.refresh_from_db()
        self.assertEqual(self.payee.first_name, "Sam")

    def test_owner_can_update(self):
        login(self.client, self.admin)
        response = self.client.post(
            f"/payees/{self.payee.id}/update",
            {"first_name": "pat", "last_name": "jones", "email": "pat@example.com"},
        )
        self.assertRedirects(response, f"/payees/{self.payee.id}", fetch_redirect_response=False)
        self.payee.refresh_from_db()
        self.assertEqual(self.payee.first_name, "Pat")
        self.assertEqual(self.payee.email, "pat@example.com")


class PayeeFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.admin = make_user("admin@example.com")
        self.payee = Payee.objects.create(user=self.admin, first_name="Sam", last_name="Smith")
        login(self.client, self.admin)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    def test_create_form_includes_working_csrf_token(self):
        token = self._csrf_token("/payees/new")
        response = self.client.post(
            "/payees", {"first_name": "Pat", "last_name": "Jones", "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 302)

    def test_update_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/payees/{self.payee.id}")
        response = self.client.post(
            f"/payees/{self.payee.id}/update",
            {"first_name": "Pat", "last_name": "Jones", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)
