"""Profile, password, first-run setup and My Data over the API."""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from billing.models import Payee
from students.models import Student

from . import data_views
from .models import User

ME = "/api/v1/auth/me"
PASSWORD = "/api/v1/auth/password"
SETUP = "/api/v1/setup"
EXPORT = "/api/v1/data/export"
IMPORT = "/api/v1/data/import"
STRONG = "a-Much-Better-Passw0rd"


def make_user(email="tutor@example.com", password="Old-passw0rd!", **extra):
    return User.objects.create_user(email=email, password=password, first_name="Ada", last_name="Lovelace", **extra)


def csrf_client():
    """A client that enforces CSRF and has fetched a token, as the browser app does."""
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client, token


def cookie_login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_updates_name_email_and_address(self):
        response = self.client.patch(
            ME, {"first_name": "Grace", "email": "grace@example.com", "address": "  1 Lab Lane  "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Grace")
        self.assertEqual(self.user.email, "grace@example.com")
        self.assertEqual(self.user.address, "1 Lab Lane")
        self.assertEqual(response.json()["email"], "grace@example.com")

    def test_blank_address_is_stored_as_null(self):
        self.client.patch(ME, {"address": "   "}, format="json")
        self.user.refresh_from_db()
        self.assertIsNone(self.user.address)

    def test_email_taken_by_another_account_is_rejected_case_insensitively(self):
        make_user("taken@example.com")
        response = self.client.patch(ME, {"email": "TAKEN@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    def test_keeping_own_email_is_allowed(self):
        response = self.client.patch(ME, {"email": self.user.email, "first_name": "Ada"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_grant_self_privileges(self):
        self.client.patch(
            ME, {"is_staff": True, "is_superuser": True, "is_active": False, "assistant_daily_limit": None}, format="json"
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.assistant_daily_limit, 1)

    def test_cookie_auth_needs_csrf_token(self):
        client, token = csrf_client()
        cookie_login(client, self.user)
        self.assertEqual(client.patch(ME, {"first_name": "X"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        response = client.patch(ME, {"first_name": "X"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PasswordChangeTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_changes_password_and_sets_fresh_cookies(self):
        response = self.client.post(PASSWORD, {"current_password": "Old-passw0rd!", "new_password": STRONG}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG))
        self.assertTrue(response.cookies["access_token"].value)
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_signs_out_other_sessions(self):
        other_session = RefreshToken.for_user(self.user)
        self.client.post(PASSWORD, {"current_password": "Old-passw0rd!", "new_password": STRONG}, format="json")

        self.assertTrue(BlacklistedToken.objects.filter(token__jti=other_session["jti"]).exists())
        response = APIClient().post("/api/v1/auth/refresh", {"refresh": str(other_session)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_current_password_is_rejected(self):
        response = self.client.post(PASSWORD, {"current_password": "wrong", "new_password": STRONG}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-passw0rd!"))

    def test_weak_new_password_is_rejected(self):
        response = self.client.post(PASSWORD, {"current_password": "Old-passw0rd!", "new_password": "123"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.json())

    def test_requires_authentication(self):
        response = APIClient().post(PASSWORD, {"current_password": "x", "new_password": STRONG}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cookie_auth_needs_csrf_token(self):
        client, _ = csrf_client()
        cookie_login(client, self.user)
        response = client.post(PASSWORD, {"current_password": "Old-passw0rd!", "new_password": STRONG}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SetupTests(APITestCase):
    def body(self, **overrides):
        return {"first_name": " jane ", "last_name": "doe", "email": "jane@example.com", "password": STRONG, **overrides}

    def test_reports_needed_only_while_no_account_exists(self):
        self.assertEqual(self.client.get(SETUP).json(), {"needed": True})
        make_user()
        self.assertEqual(self.client.get(SETUP).json(), {"needed": False})

    def test_creates_first_account(self):
        client, token = csrf_client()
        response = client.post(SETUP, self.body(), format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="jane@example.com")
        self.assertEqual((user.first_name, user.last_name), ("Jane", "Doe"))
        self.assertTrue(user.check_password(STRONG))
        self.assertFalse(user.is_staff)

    def test_conflict_once_an_account_exists(self):
        make_user()
        client, token = csrf_client()
        response = client.post(SETUP, self.body(), format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(User.objects.filter(email="jane@example.com").exists())

    def test_weak_password_is_rejected(self):
        client, token = csrf_client()
        response = client.post(SETUP, self.body(password="password"), format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_needs_csrf_token(self):
        client, _ = csrf_client()
        self.assertEqual(client.post(SETUP, self.body(), format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.exists())


class DataExportTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_downloads_only_own_rows_as_attachment(self):
        Payee.objects.create(user=self.user, first_name="Mine", last_name="Payee")
        Payee.objects.create(user=make_user("other@example.com"), first_name="Theirs", last_name="Payee")

        response = self.client.get(EXPORT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attachment; filename="tutorhub_export_', response["Content-Disposition"])
        data = json.loads(response.content)
        self.assertEqual([p["first_name"] for p in data["payees"]], ["Mine"])
        self.assertNotIn("password", response.content.decode())

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(EXPORT).status_code, status.HTTP_401_UNAUTHORIZED)


class DataImportTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def upload(self, content, client=None, **extra):
        return (client or self.client).post(
            IMPORT, {"file": SimpleUploadedFile("export.json", content, content_type="application/json")}, **extra
        )

    def test_replaces_data_and_returns_counts(self):
        Student.objects.create(user=self.user, first_name="Old", last_name="Student")
        export = {
            "payees": [{"id": "p1", "first_name": "New", "last_name": "Payee"}],
            "students": [{"id": "s1", "first_name": "New", "last_name": "Student", "payee_id": "p1"}],
            "sessions": [],
            "payments": [],
        }
        response = self.upload(json.dumps(export).encode())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"payees": 1, "students": 1, "sessions": 0, "payments": 0})
        self.assertEqual(list(Student.objects.filter(user=self.user).values_list("first_name", flat=True)), ["New"])

    def test_round_trips_an_export(self):
        Student.objects.create(user=self.user, first_name="Kept", last_name="Student")
        exported = self.client.get(EXPORT).content
        self.assertEqual(self.upload(exported).status_code, status.HTTP_200_OK)
        self.assertEqual(list(Student.objects.filter(user=self.user).values_list("first_name", flat=True)), ["Kept"])

    def test_invalid_json_is_rejected_and_keeps_data(self):
        Student.objects.create(user=self.user, first_name="Kept", last_name="Student")
        response = self.upload(b"{not json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Student.objects.filter(first_name="Kept").exists())

    def test_non_object_json_is_rejected(self):
        self.assertEqual(self.upload(b"[]").status_code, status.HTTP_400_BAD_REQUEST)

    def test_bad_reference_rolls_back(self):
        Student.objects.create(user=self.user, first_name="Kept", last_name="Student")
        export = {"payees": [], "students": [{"id": "s1", "first_name": "X", "last_name": "Y", "payee_id": "missing"}]}
        response = self.upload(json.dumps(export).encode())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(Student.objects.filter(user=self.user).values_list("first_name", flat=True)), ["Kept"])

    def test_missing_file_is_rejected(self):
        self.assertEqual(self.client.post(IMPORT, {}).status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_file_is_rejected(self):
        original = data_views.MAX_IMPORT_BYTES
        data_views.MAX_IMPORT_BYTES = 10
        try:
            response = self.upload(b'{"payees": []}')
        finally:
            data_views.MAX_IMPORT_BYTES = original
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cookie_auth_needs_csrf_token(self):
        Student.objects.create(user=self.user, first_name="Kept", last_name="Student")
        client, _ = csrf_client()
        cookie_login(client, self.user)
        response = self.upload(b'{"payees": []}', client=client)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Student.objects.filter(first_name="Kept").exists())
