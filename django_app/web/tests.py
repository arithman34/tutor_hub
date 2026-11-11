from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import services


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="s3cret-pass", first_name="A", last_name="B", **extra)


class AuthFormsCsrfTests(TestCase):
    """Client() doesn't enforce CSRF, so these use a CSRF-enforcing client —
    see web/test_students.py:StudentFormsCsrfTests for why."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_login_form_includes_working_csrf_token(self):
        self.client.get("/login")
        token = self.client.cookies["csrftoken"].value
        user = make_user("tutor@example.com")
        response = self.client.post("/login", {"email": user.email, "password": "s3cret-pass", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_logout_form_includes_working_csrf_token(self):
        user = make_user("tutor@example.com")
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        self.client.get("/dashboard")
        token = self.client.cookies["csrftoken"].value
        response = self.client.post("/logout", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)


class LoginPageTests(TestCase):
    def test_get_renders_login_form(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_post_with_valid_credentials_sets_cookies_and_redirects(self):
        make_user("tutor@example.com")
        response = self.client.post("/login", {"email": "tutor@example.com", "password": "s3cret-pass"})
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])

    def test_post_with_wrong_password_shows_error(self):
        make_user("tutor@example.com")
        response = self.client.post("/login", {"email": "tutor@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid email or password", status_code=400)

    def test_post_for_inactive_user_is_rejected(self):
        user = make_user("tutor@example.com", is_active=False)
        response = self.client.post("/login", {"email": user.email, "password": "s3cret-pass"})
        self.assertEqual(response.status_code, 400)


class LogoutTests(TestCase):
    def test_logout_clears_cookies_and_blacklists_refresh_token(self):
        user = make_user("tutor@example.com")
        refresh = RefreshToken.for_user(user)
        self.client.cookies["access_token"] = str(refresh.access_token)
        self.client.cookies["refresh_token"] = str(refresh)

        response = self.client.post("/logout")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")

        # The blacklisted refresh token should no longer authenticate.
        dashboard_response = self.client.get("/dashboard")
        self.assertRedirects(dashboard_response, "/login", fetch_redirect_response=False)


class DashboardAccessTests(TestCase):
    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/dashboard")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_authenticated_tutor_sees_dashboard(self):
        user = make_user("tutor@example.com")
        refresh = RefreshToken.for_user(user)
        self.client.cookies["access_token"] = str(refresh.access_token)

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")

    def test_expired_access_token_refreshes_via_refresh_cookie(self):
        user = make_user("tutor@example.com")
        refresh = RefreshToken.for_user(user)
        self.client.cookies["access_token"] = "not-a-valid-token"
        self.client.cookies["refresh_token"] = str(refresh)

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)

    def test_invalid_tokens_redirect_to_login(self):
        self.client.cookies["access_token"] = "garbage"
        self.client.cookies["refresh_token"] = "also-garbage"
        response = self.client.get("/dashboard")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)


class DashboardStatsTests(TestCase):
    def test_stats_reflect_own_data_only(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        payee = Payee.objects.create(user=tutor, first_name="Jo", last_name="Payer")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", payee=payee, hourly_rate=30)
        other_payee = Payee.objects.create(user=other, first_name="Lee", last_name="Other")
        other_student = Student.objects.create(user=other, first_name="Pat", last_name="Jones", payee=other_payee, hourly_rate=99)

        now = timezone.now()
        for owner, s in ((tutor, student), (other, other_student), (other, other_student)):
            Session.objects.create(
                user=owner, student=s, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=2)
            )
        Payment.objects.create(user=tutor, payee=payee, amount=Decimal("100.00"), payment_date=now)
        Payment.objects.create(user=other, payee=other_payee, amount=Decimal("500.00"), payment_date=now)

        stats = services.get_dashboard_stats(tutor)
        self.assertEqual(stats["active_students"], 1)
        self.assertEqual(stats["sessions_this_month"], 1)
        self.assertEqual(stats["hours_this_month"], 2.0)
        self.assertEqual(stats["revenue_this_month"], 100.0)
        self.assertEqual(stats["revenue_alltime"], 100.0)
        # 2h * £30 = £60 billed, £100 paid: Jo is in credit, nobody owes.
        self.assertEqual(stats["outstanding_total"], 0)
        self.assertEqual(stats["outstanding_payees"], 0)

    def test_outstanding_sums_only_payees_who_owe(self):
        tutor = make_user("tutor@example.com")
        now = timezone.now()
        for name, rate, paid in (("Owes", 40, "10.00"), ("Also", 20, "0.00"), ("Credit", 10, "100.00")):
            payee = Payee.objects.create(user=tutor, first_name=name, last_name="P")
            student = Student.objects.create(user=tutor, first_name=name, last_name="S", payee=payee, hourly_rate=rate)
            Session.objects.create(
                user=tutor, student=student, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=1)
            )
            Payment.objects.create(user=tutor, payee=payee, amount=Decimal(paid), payment_date=now)

        stats = services.get_dashboard_stats(tutor)
        # Owes: 40 - 10 = 30, Also: 20 - 0 = 20, Credit is +90 and excluded.
        self.assertEqual(stats["outstanding_total"], 50.0)
        self.assertEqual(stats["outstanding_payees"], 2)

    def test_dashboard_renders_business_stats(self):
        user = make_user("tutor@example.com")
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)

        response = self.client.get("/dashboard")
        self.assertContains(response, "Revenue All-Time")
        self.assertContains(response, "Outstanding")
        self.assertNotContains(response, "Tutor Payouts")
