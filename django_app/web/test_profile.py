from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class ProfilePageTests(TestCase):
    def test_shows_current_details(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/profile")
        self.assertContains(response, "tutor@example.com")

    def test_tutor_cannot_see_role_select(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/profile")
        self.assertNotContains(response, "<select name=\"role\"")

    def test_admin_sees_role_select(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/profile")
        self.assertContains(response, "<select name=\"role\"")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/profile")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_success_flash_shown(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/profile", {"success": "details"})
        self.assertContains(response, "Profile updated successfully.")


class ProfileUpdateTests(TestCase):
    def test_updates_name_email_and_address(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.post(
            "/profile/update",
            {"first_name": "New", "last_name": "Name", "email": "new@example.com", "address": "  123 Main St  "},
        )
        self.assertRedirects(response, "/profile?success=details", fetch_redirect_response=False)
        tutor.refresh_from_db()
        self.assertEqual(tutor.first_name, "New")
        self.assertEqual(tutor.email, "new@example.com")
        self.assertEqual(tutor.address, "123 Main St")

    def test_email_already_taken_redirects_with_error(self):
        make_user("taken@example.com")
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.post(
            "/profile/update", {"first_name": "A", "last_name": "B", "email": "taken@example.com"}
        )
        self.assertRedirects(response, "/profile?error=email_taken", fetch_redirect_response=False)
        tutor.refresh_from_db()
        self.assertEqual(tutor.email, "tutor@example.com")

    def test_non_admin_cannot_change_own_role(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        self.client.post(
            "/profile/update", {"first_name": "A", "last_name": "B", "email": "tutor@example.com", "role": "admin_tutor"}
        )
        tutor.refresh_from_db()
        self.assertEqual(tutor.role, UserRole.TUTOR)

    def test_admin_tutor_can_change_own_role(self):
        admin_tutor = make_user("admin@example.com", UserRole.ADMIN_TUTOR)
        login(self.client, admin_tutor)
        self.client.post(
            "/profile/update",
            {"first_name": "A", "last_name": "B", "email": "admin@example.com", "role": "admin_tutor"},
        )
        admin_tutor.refresh_from_db()
        self.assertEqual(admin_tutor.role, UserRole.ADMIN_TUTOR)


class ProfilePasswordTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        login(self.client, self.tutor)

    def test_correct_current_password_changes_it(self):
        response = self.client.post(
            "/profile/password",
            {"current_password": "x", "new_password": "newpass123", "confirm_password": "newpass123"},
        )
        self.assertRedirects(response, "/profile?success=password", fetch_redirect_response=False)
        self.tutor.refresh_from_db()
        self.assertTrue(self.tutor.check_password("newpass123"))

    def test_wrong_current_password_rejected(self):
        response = self.client.post(
            "/profile/password",
            {"current_password": "wrong", "new_password": "newpass123", "confirm_password": "newpass123"},
        )
        self.assertRedirects(response, "/profile?error=wrong_password", fetch_redirect_response=False)
        self.tutor.refresh_from_db()
        self.assertTrue(self.tutor.check_password("x"))

    def test_mismatched_new_passwords_rejected(self):
        response = self.client.post(
            "/profile/password",
            {"current_password": "x", "new_password": "newpass123", "confirm_password": "different"},
        )
        self.assertRedirects(response, "/profile?error=password_mismatch", fetch_redirect_response=False)


class ProfileFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = make_user("tutor@example.com")
        login(self.client, self.tutor)

    def _csrf_token(self):
        self.client.get("/profile")
        return self.client.cookies["csrftoken"].value

    def test_update_form_includes_working_csrf_token(self):
        token = self._csrf_token()
        response = self.client.post(
            "/profile/update",
            {"first_name": "A", "last_name": "B", "email": "tutor@example.com", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)

    def test_password_form_includes_working_csrf_token(self):
        token = self._csrf_token()
        response = self.client.post(
            "/profile/password",
            {
                "current_password": "x",
                "new_password": "newpass123",
                "confirm_password": "newpass123",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)
