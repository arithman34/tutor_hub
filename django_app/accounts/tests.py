from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class UserManagerTests(TestCase):
    def test_create_user_hashes_password_and_defaults_to_non_staff(self):
        user = User.objects.create_user(
            email="tutor@example.com", password="s3cret-pass", first_name="Ada", last_name="Lovelace"
        )
        self.assertNotEqual(user.password, "s3cret-pass")
        self.assertTrue(user.check_password("s3cret-pass"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="x", first_name="A", last_name="B")

    def test_create_superuser_sets_staff_flags(self):
        user = User.objects.create_superuser(email="admin@example.com", password="s3cret-pass", first_name="Ada", last_name="Lovelace")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class AuthEndpointTests(APITestCase):
    def setUp(self):
        self.password = "s3cret-pass"
        self.user = User.objects.create_user(
            email="tutor@example.com", password=self.password, first_name="Ada", last_name="Lovelace"
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
