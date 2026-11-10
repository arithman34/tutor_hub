import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class AdminUsersPageTests(TestCase):
    def test_admin_sees_tutors(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        make_user("tutor@example.com")
        login(self.client, admin)
        response = self.client.get("/admin/users")
        self.assertContains(response, "tutor@example.com")

    def test_tutor_redirected_to_dashboard(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/admin/users")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/admin/users")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_tutor_with_data_is_not_deletable(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        login(self.client, admin)
        response = self.client.get("/admin/users")
        self.assertContains(response, "Tutor has linked data and cannot be deleted")

    def test_tutor_without_data_is_deletable(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        make_user("tutor@example.com")
        login(self.client, admin)
        response = self.client.get("/admin/users")
        self.assertNotContains(response, "Tutor has linked data and cannot be deleted")


class AdminUsersCreateTests(TestCase):
    @patch("web.admin_views.resend.Emails.send")
    def test_admin_creates_tutor_with_temp_password_and_sends_email(self, mock_send):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.post(
            "/admin/users",
            {"first_name": "new", "last_name": "tutor", "email": "newtutor@example.com", "payout_type": "hourly", "payout_hourly_rate": "25"},
        )
        self.assertRedirects(response, "/admin/users", fetch_redirect_response=False)
        tutor = User.objects.get(email="newtutor@example.com")
        self.assertEqual(tutor.first_name, "New")
        self.assertEqual(tutor.role, UserRole.TUTOR)
        self.assertEqual(tutor.payout_hourly_rate, 25.0)
        mock_send.assert_called_once()

    def test_duplicate_email_redirects_with_error(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        make_user("existing@example.com")
        login(self.client, admin)
        response = self.client.post("/admin/users", {"first_name": "A", "last_name": "B", "email": "existing@example.com"})
        self.assertRedirects(response, "/admin/users/new?error=email_taken", fetch_redirect_response=False)

    def test_tutor_cannot_create_user(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.post("/admin/users", {"first_name": "A", "last_name": "B", "email": "x@example.com"})
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(email="x@example.com").exists())


class AdminToggleActiveTests(TestCase):
    def test_admin_can_toggle_tutor_active(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        login(self.client, admin)
        response = self.client.post(f"/admin/users/{tutor.id}/toggle-active")
        self.assertRedirects(response, "/admin/users", fetch_redirect_response=False)
        tutor.refresh_from_db()
        self.assertFalse(tutor.is_active)


class AdminUpdatePayoutTests(TestCase):
    def test_admin_can_update_payout(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        login(self.client, admin)
        response = self.client.post(f"/admin/users/{tutor.id}/update-payout", {"payout_type": "percentage", "payout_percentage": "40"})
        self.assertRedirects(response, "/admin/users", fetch_redirect_response=False)
        tutor.refresh_from_db()
        self.assertEqual(tutor.payout_type, "percentage")
        self.assertEqual(tutor.payout_percentage, 40.0)


class AdminDeleteTutorTests(TestCase):
    def test_admin_can_delete_tutor_without_data(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        login(self.client, admin)
        response = self.client.post(f"/admin/users/{tutor.id}/delete")
        self.assertRedirects(response, "/admin/users", fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(id=tutor.id).exists())

    def test_admin_cannot_delete_tutor_with_data(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        login(self.client, admin)
        response = self.client.post(f"/admin/users/{tutor.id}/delete")
        self.assertRedirects(response, "/admin/users", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(id=tutor.id).exists())


class AdminDataPageTests(TestCase):
    def test_admin_sees_data_page(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/admin/data")
        self.assertContains(response, "Data Management")

    def test_tutor_redirected_away(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/admin/data")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)


class AdminExportTests(TestCase):
    def test_export_contains_all_data(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        payee = Payee.objects.create(user=admin, first_name="Pay", last_name="Ee")
        student = Student.objects.create(user=tutor, payee=payee, first_name="Sam", last_name="Smith")
        now = timezone.now()
        Session.objects.create(user=tutor, student=student, session_date=now, session_start_time=now, session_end_time=now)
        Payment.objects.create(user=admin, payee=payee, amount=50, payment_date=now)

        login(self.client, admin)
        response = self.client.get("/admin/data/export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = json.loads(response.content)
        self.assertEqual(len(data["users"]), 2)
        self.assertEqual(len(data["payees"]), 1)
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(len(data["payments"]), 1)
        self.assertIn("password", data["users"][0])


class AdminImportTests(TestCase):
    def test_round_trip_export_then_import_preserves_data(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        tutor = make_user("tutor@example.com")
        payee = Payee.objects.create(user=admin, first_name="Pay", last_name="Ee")
        student = Student.objects.create(user=tutor, payee=payee, first_name="Sam", last_name="Smith", hourly_rate=20)
        now = timezone.now()
        Session.objects.create(user=tutor, student=student, session_date=now, session_start_time=now, session_end_time=now, work_covered="fractions")
        Payment.objects.create(user=admin, payee=payee, amount=50, payment_date=now, payment_reference="ref-1")

        login(self.client, admin)
        export_response = self.client.get("/admin/data/export")
        exported = export_response.content

        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("export.json", exported, content_type="application/json")
        response = self.client.post("/admin/data/import", {"file": upload})
        self.assertRedirects(response, "/admin/data?imported=1", fetch_redirect_response=False)

        self.assertEqual(User.objects.count(), 2)
        restored_student = Student.objects.get(first_name="Sam")
        self.assertEqual(restored_student.hourly_rate, 20)
        self.assertEqual(Session.objects.get().work_covered, "fractions")
        self.assertEqual(Payment.objects.get().payment_reference, "ref-1")
        # The admin's own password/session must survive the import — re-login works.
        restored_admin = User.objects.get(email="admin@example.com")
        self.assertTrue(restored_admin.check_password("x"))

    def test_invalid_json_redirects_with_error_and_keeps_existing_data(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)

        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("bad.json", b"not json", content_type="application/json")
        response = self.client.post("/admin/data/import", {"file": upload})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/admin/data?error="))
        self.assertTrue(User.objects.filter(id=admin.id).exists())

    def test_tutor_cannot_import(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)

        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("export.json", b"{}", content_type="application/json")
        response = self.client.post("/admin/data/import", {"file": upload})
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(id=tutor.id).exists())


class AdminFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.admin = make_user("admin@example.com", UserRole.ADMIN)
        self.tutor = make_user("tutor@example.com")
        login(self.client, self.admin)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    @patch("web.admin_views.resend.Emails.send")
    def test_create_form_includes_working_csrf_token(self, mock_send):
        token = self._csrf_token("/admin/users/new")
        response = self.client.post(
            "/admin/users",
            {"first_name": "A", "last_name": "B", "email": "x@example.com", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)

    def test_toggle_active_form_includes_working_csrf_token(self):
        token = self._csrf_token("/admin/users")
        response = self.client.post(f"/admin/users/{self.tutor.id}/toggle-active", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_payout_form_includes_working_csrf_token(self):
        token = self._csrf_token("/admin/users")
        response = self.client.post(
            f"/admin/users/{self.tutor.id}/update-payout", {"payout_type": "hourly", "payout_hourly_rate": "10", "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_form_includes_working_csrf_token(self):
        token = self._csrf_token("/admin/users")
        response = self.client.post(f"/admin/users/{self.tutor.id}/delete", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_import_form_includes_working_csrf_token(self):
        token = self._csrf_token("/admin/data")
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("export.json", b"{}", content_type="application/json")
        response = self.client.post("/admin/data/import", {"file": upload, "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
