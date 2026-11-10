from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User, UserRole


class UserManagerTests(TestCase):
    def test_create_user_hashes_password_and_defaults_to_non_staff(self):
        user = User.objects.create_user(
            email="tutor@example.com", password="s3cret-pass", first_name="Ada", last_name="Lovelace", role=UserRole.TUTOR
        )
        self.assertNotEqual(user.password, "s3cret-pass")
        self.assertTrue(user.check_password("s3cret-pass"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="x", first_name="A", last_name="B", role=UserRole.TUTOR)

    def test_create_superuser_sets_admin_role_and_flags(self):
        user = User.objects.create_superuser(email="admin@example.com", password="s3cret-pass", first_name="Ada", last_name="Lovelace")
        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class UserRolePropertiesTests(TestCase):
    def test_is_admin_true_for_admin_and_admin_tutor(self):
        admin = User.objects.create_user(email="a@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN)
        admin_tutor = User.objects.create_user(email="c@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN_TUTOR)
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin_tutor.is_admin)

    def test_is_admin_false_for_plain_tutor(self):
        tutor = User.objects.create_user(email="b@example.com", password="x", first_name="A", last_name="B", role=UserRole.TUTOR)
        self.assertFalse(tutor.is_admin)
        self.assertTrue(tutor.is_tutor)


class OneAdminConstraintTests(TestCase):
    def test_only_one_plain_admin_allowed(self):
        User.objects.create_user(email="admin1@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN)
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="admin2@example.com", password="x", first_name="C", last_name="D", role=UserRole.ADMIN)

    def test_multiple_admin_tutors_allowed(self):
        User.objects.create_user(email="at1@example.com", password="x", first_name="A", last_name="B", role=UserRole.ADMIN_TUTOR)
        User.objects.create_user(email="at2@example.com", password="x", first_name="C", last_name="D", role=UserRole.ADMIN_TUTOR)
        self.assertEqual(User.objects.filter(role=UserRole.ADMIN_TUTOR).count(), 2)


class AuthEndpointTests(APITestCase):
    def setUp(self):
        self.password = "s3cret-pass"
        self.user = User.objects.create_user(
            email="tutor@example.com", password=self.password, first_name="Ada", last_name="Lovelace", role=UserRole.TUTOR
        )

    def test_login_with_valid_credentials_returns_token_pair(self):
        response = self.client.post(reverse("token_obtain_pair"), {"email": self.user.email, "password": self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_is_rejected(self):
        response = self.client.post(reverse("token_obtain_pair"), {"email": self.user.email, "password": "wrong"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_for_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(reverse("token_obtain_pair"), {"email": self.user.email, "password": self.password})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_token(self):
        login = self.client.post(reverse("token_obtain_pair"), {"email": self.user.email, "password": self.password})
        refresh_response = self.client.post(reverse("token_refresh"), {"refresh": login.data["refresh"]})
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post(reverse("token_obtain_pair"), {"email": self.user.email, "password": self.password})
        refresh_token = login.data["refresh"]

        logout_response = self.client.post(reverse("token_blacklist"), {"refresh": refresh_token})
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        reuse_response = self.client.post(reverse("token_refresh"), {"refresh": refresh_token})
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)
