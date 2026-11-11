import json
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from .data_transfer import build_full_backup, build_user_export, import_user_data, restore_full_backup


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="s3cret-pass", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


def seed(user, name="Sam"):
    """One payee paying for one student with one session and one payment."""
    now = timezone.now()
    payee = Payee.objects.create(user=user, first_name=f"{name}-payee", last_name="P", email=f"{name.lower()}@example.com")
    student = Student.objects.create(user=user, first_name=name, last_name="S", payee=payee, hourly_rate=30)
    session = Session.objects.create(
        user=user,
        student=student,
        session_date=now,
        session_start_time=now,
        session_end_time=now + timedelta(hours=1),
        work_covered=f"{name} fractions",
    )
    payment = Payment.objects.create(user=user, payee=payee, amount=Decimal("45.50"), payment_date=now, payment_reference="ref")
    return payee, student, session, payment


def upload(data, name="export.json"):
    raw = data if isinstance(data, bytes) else json.dumps(data).encode()
    return SimpleUploadedFile(name, raw, content_type="application/json")


class UserExportTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other = make_user("other@example.com")
        seed(self.owner, "Sam")
        seed(self.other, "Pat")

    def test_contains_only_own_rows(self):
        data = build_user_export(self.owner)
        self.assertEqual([s["first_name"] for s in data["students"]], ["Sam"])
        self.assertEqual(len(data["payees"]), 1)
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(len(data["payments"]), 1)
        self.assertNotIn("Pat", json.dumps(data))

    def test_contains_no_account_or_credential_data(self):
        data = build_user_export(self.owner)
        self.assertNotIn("users", data)
        dumped = json.dumps(data)
        self.assertNotIn("password", dumped)
        self.assertNotIn("user_id", dumped)
        self.assertNotIn(self.owner.password, dumped)

    def test_download_endpoint(self):
        login(self.client, self.owner)
        response = self.client.get("/data/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        data = json.loads(response.content)
        self.assertEqual([s["first_name"] for s in data["students"]], ["Sam"])


class UserImportTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other = make_user("other@example.com")

    def test_round_trip_restores_own_data(self):
        seed(self.owner, "Sam")
        data = build_user_export(self.owner)
        Student.objects.filter(user=self.owner).update(first_name="Changed")

        counts = import_user_data(self.owner, data)

        self.assertEqual(counts, {"payees": 1, "students": 1, "sessions": 1, "payments": 1})
        student = Student.objects.get(user=self.owner)
        self.assertEqual(student.first_name, "Sam")
        self.assertEqual(student.payee.user, self.owner)
        session = Session.objects.get(user=self.owner)
        self.assertEqual(session.student, student)
        self.assertEqual(session.work_covered, "Sam fractions")
        payment = Payment.objects.get(user=self.owner)
        self.assertEqual(payment.payee, student.payee)
        self.assertEqual(payment.amount, Decimal("45.50"))

    def test_never_touches_another_accounts_rows(self):
        seed(self.owner, "Sam")
        other_rows = seed(self.other, "Pat")
        import_user_data(self.owner, {"payees": [], "students": [], "sessions": [], "payments": []})

        self.assertFalse(Student.objects.filter(user=self.owner).exists())
        for row in other_rows:
            self.assertTrue(type(row).objects.filter(id=row.id).exists())

    def test_importing_another_accounts_export_copies_rather_than_steals(self):
        """Even with the same ids in the file, the import creates fresh rows
        owned by the importer; the original owner's rows are untouched."""
        _, other_student, _, _ = seed(self.other, "Pat")
        data = build_user_export(self.other)

        import_user_data(self.owner, data)

        other_student.refresh_from_db()
        self.assertEqual(other_student.user, self.other)
        mine = Student.objects.get(user=self.owner)
        self.assertNotEqual(mine.id, other_student.id)
        self.assertEqual(Student.objects.filter(first_name="Pat").count(), 2)

    def test_file_user_ids_are_ignored(self):
        seed(self.owner, "Sam")
        data = build_user_export(self.owner)
        for kind in ("payees", "students", "sessions", "payments"):
            for row in data[kind]:
                row["user_id"] = str(self.other.id)

        import_user_data(self.owner, data)

        self.assertEqual(Student.objects.filter(user=self.owner).count(), 1)
        self.assertFalse(Student.objects.filter(user=self.other).exists())

    def test_reference_to_row_outside_file_is_rejected_and_rolled_back(self):
        seed(self.owner, "Sam")
        foreign_payee, _, _, _ = seed(self.other, "Pat")
        data = build_user_export(self.owner)
        data["students"][0]["payee_id"] = str(foreign_payee.id)

        with self.assertRaises(ValueError):
            import_user_data(self.owner, data)

        # Rolled back: the owner's original data is still there, unchanged.
        student = Student.objects.get(user=self.owner)
        self.assertEqual(student.payee.user, self.owner)

    def test_upload_endpoint_replaces_data(self):
        seed(self.owner, "Sam")
        data = build_user_export(self.owner)
        data["students"][0]["first_name"] = "Lok"
        login(self.client, self.owner)

        response = self.client.post("/data/import", {"file": upload(data)})

        self.assertRedirects(response, "/data?imported=1", fetch_redirect_response=False)
        self.assertEqual(Student.objects.get(user=self.owner).first_name, "Lok")

    def test_invalid_json_redirects_with_error_and_keeps_existing_data(self):
        seed(self.owner, "Sam")
        login(self.client, self.owner)
        response = self.client.post("/data/import", {"file": upload(b"not json")})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/data?error="))
        self.assertTrue(Student.objects.filter(user=self.owner, first_name="Sam").exists())

    def test_missing_file_redirects_with_error(self):
        login(self.client, self.owner)
        response = self.client.post("/data/import", {})
        self.assertTrue(response["Location"].startswith("/data?error="))


class DataPageTests(TestCase):
    def test_renders_for_any_account(self):
        login(self.client, make_user("owner@example.com"))
        response = self.client.get("/data")
        self.assertContains(response, "My Data")
        self.assertContains(response, "/data/export")

    def test_unauthenticated_redirects_to_login(self):
        for path in ("/data", "/data/export"):
            response = self.client.get(path)
            self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_old_admin_routes_are_gone(self):
        login(self.client, make_user("owner@example.com"))
        for path in ("/admin/users", "/admin/data", "/admin/data/export"):
            self.assertEqual(self.client.get(path).status_code, 404, path)


class DataFormsCsrfTests(TestCase):
    def test_import_form_includes_working_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        owner = make_user("owner@example.com")
        login(client, owner)
        client.get("/data")
        token = client.cookies["csrftoken"].value
        response = client.post("/data/import", {"file": upload(build_user_export(owner)), "csrfmiddlewaretoken": token})
        self.assertRedirects(response, "/data?imported=1", fetch_redirect_response=False)

    def test_import_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        owner = make_user("owner@example.com")
        seed(owner, "Sam")
        login(client, owner)
        response = client.post("/data/import", {"file": upload({"students": []})})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Student.objects.filter(user=owner).exists())


class FullBackupTests(TestCase):
    """The operator's disaster-recovery path (management commands only)."""

    def test_round_trip_restores_every_account(self):
        owner = make_user("owner@example.com")
        other = make_user("other@example.com")
        seed(owner, "Sam")
        seed(other, "Pat")
        backup = json.loads(json.dumps(build_full_backup()))

        Student.objects.all().delete()
        restore_full_backup(backup)

        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Student.objects.get(first_name="Sam").user.email, "owner@example.com")
        self.assertEqual(Student.objects.get(first_name="Pat").user.email, "other@example.com")
        self.assertTrue(User.objects.get(email="owner@example.com").check_password("s3cret-pass"))

    def test_restore_ignores_retired_role_and_payout_fields(self):
        owner = make_user("owner@example.com")
        backup = json.loads(json.dumps(build_full_backup()))
        backup["users"][0].update({"role": "admin", "payout_type": "hourly", "payout_hourly_rate": 20})

        restore_full_backup(backup)

        self.assertEqual(User.objects.get().email, owner.email)
