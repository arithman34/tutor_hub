from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from . import services


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="s3cret-pass", first_name="A", last_name="B", role=role, **extra)


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
    def test_tutor_stats_reflect_their_own_data_only(self):
        tutor = make_user("tutor@example.com", payout_hourly_rate=20)
        other_tutor = make_user("other@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        Student.objects.create(user=other_tutor, first_name="Pat", last_name="Jones", is_active=True)

        now = timezone.now()
        Session.objects.create(
            user=tutor,
            student=Student.objects.get(user=tutor),
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
        )

        stats = services.get_tutor_stats(tutor)
        self.assertEqual(stats["active_students"], 1)
        self.assertEqual(stats["sessions_this_month"], 1)
        self.assertEqual(stats["amount_owed"], 20.0)

    def test_admin_stats_compute_revenue_and_profit_margin(self):
        tutor = make_user("tutor@example.com", payout_hourly_rate=20, payout_type="hourly")
        payee = Payee.objects.create(user=tutor, first_name="Jo", last_name="Payer")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", payee=payee)

        now = timezone.now()
        Session.objects.create(
            user=tutor, student=student, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=2)
        )
        Payment.objects.create(user=tutor, payee=payee, amount=Decimal("100.00"), payment_date=now)

        stats = services.get_admin_stats()
        self.assertEqual(stats["revenue_this_month"], 100.0)
        # 2 hours * £20/hr = £40 obligation, profit = 100 - 40 = 60
        self.assertEqual(stats["total_payout_obligations"], 40.0)
        self.assertEqual(stats["profit_margin"], 60.0)

    def test_admin_sees_admin_dashboard_not_tutor_dashboard(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        refresh = RefreshToken.for_user(admin)
        self.client.cookies["access_token"] = str(refresh.access_token)

        response = self.client.get("/dashboard")
        self.assertContains(response, "Revenue All-Time")
