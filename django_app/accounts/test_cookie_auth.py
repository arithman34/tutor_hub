"""Cookie-based API auth for the browser app: the cookie endpoints, the
header-or-cookie authentication class, its CSRF rule, and the schema docs.

Every client here enforces CSRF checks (Django's default test client skips
them), so a missing or broken CSRF check fails these tests.
"""

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from students.models import Student

from .models import User

CSRF = "/api/v1/auth/csrf"
LOGIN = "/api/v1/auth/cookie/login"
REFRESH = "/api/v1/auth/cookie/refresh"
LOGOUT = "/api/v1/auth/cookie/logout"
ME = "/api/v1/auth/me"
STUDENTS = "/api/v1/students/"


class CookieAuthTestCase(APITestCase):
    def setUp(self):
        self.password = "s3cret-pass"
        self.user = User.objects.create_user(
            email="tutor@example.com", password=self.password, first_name="Ada", last_name="Lovelace"
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self):
        return self.client.get(CSRF).json()["csrf_token"]

    def log_in(self):
        token = self.csrf_token()
        response = self.client.post(
            LOGIN, {"email": self.user.email, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return token


class CsrfEndpointTests(CookieAuthTestCase):
    def test_sets_cookie_and_returns_matching_token(self):
        response = self.client.get(CSRF)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("csrftoken", response.cookies)
        self.assertTrue(response.json()["csrf_token"])

    def test_is_public(self):
        self.assertEqual(APIClient().get(CSRF).status_code, status.HTTP_200_OK)


class CookieLoginTests(CookieAuthTestCase):
    def test_sets_httponly_cookies_and_returns_user_without_tokens(self):
        token = self.csrf_token()
        response = self.client.post(
            LOGIN, {"email": self.user.email, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertNotIn("access", response.json())
        self.assertNotIn("refresh", response.json())
        for name in ("access_token", "refresh_token"):
            self.assertTrue(response.cookies[name].value)
            self.assertTrue(response.cookies[name]["httponly"])
            self.assertEqual(response.cookies[name]["samesite"], "Lax")

    def test_rejected_without_csrf_token(self):
        self.client.get(CSRF)
        response = self.client.post(LOGIN, {"email": self.user.email, "password": self.password}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("access_token", response.cookies)

    def test_wrong_password_is_rejected_without_cookies(self):
        token = self.csrf_token()
        response = self.client.post(
            LOGIN, {"email": self.user.email, "password": "wrong"}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access_token", response.cookies)

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()
        token = self.csrf_token()
        response = self.client.post(
            LOGIN, {"email": self.user.email, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_access_cookie_does_not_block_login(self):
        self.client.cookies["access_token"] = "expired-or-garbage"
        self.log_in()

    @override_settings(SECURE_COOKIES=True)
    def test_cookies_are_secure_in_production(self):
        token = self.csrf_token()
        response = self.client.post(
            LOGIN, {"email": self.user.email, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertTrue(response.cookies["access_token"]["secure"])
        self.assertTrue(response.cookies["refresh_token"]["secure"])


class CookieRefreshTests(CookieAuthTestCase):
    def test_rotates_both_cookies_and_blacklists_old_refresh(self):
        token = self.log_in()
        old_refresh = self.client.cookies["refresh_token"].value

        response = self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertNotEqual(response.cookies["refresh_token"].value, old_refresh)
        self.assertTrue(response.cookies["access_token"].value)
        self.assertTrue(BlacklistedToken.objects.filter(token__token=old_refresh).exists())

    def test_new_access_cookie_works(self):
        token = self.log_in()
        self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(self.client.get(ME).status_code, status.HTTP_200_OK)

    def test_without_refresh_cookie_is_unauthorized(self):
        token = self.csrf_token()
        self.assertEqual(self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_refresh_cookie_is_unauthorized_and_cleared(self):
        token = self.csrf_token()
        self.client.cookies["refresh_token"] = "not-a-token"
        response = self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_reusing_a_rotated_refresh_token_is_rejected(self):
        token = self.log_in()
        old_refresh = self.client.cookies["refresh_token"].value
        self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token)

        self.client.cookies["refresh_token"] = old_refresh
        self.assertEqual(self.client.post(REFRESH, HTTP_X_CSRFTOKEN=token).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejected_without_csrf_token(self):
        self.log_in()
        self.assertEqual(self.client.post(REFRESH).status_code, status.HTTP_403_FORBIDDEN)


class CookieLogoutTests(CookieAuthTestCase):
    def test_blacklists_refresh_and_clears_cookies(self):
        token = self.log_in()
        refresh = self.client.cookies["refresh_token"].value

        response = self.client.post(LOGOUT, HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")
        self.assertTrue(BlacklistedToken.objects.filter(token__token=refresh).exists())
        self.assertEqual(self.client.get(ME).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_works_when_already_logged_out(self):
        token = self.csrf_token()
        self.assertEqual(self.client.post(LOGOUT, HTTP_X_CSRFTOKEN=token).status_code, status.HTTP_204_NO_CONTENT)

    def test_rejected_without_csrf_token(self):
        self.log_in()
        self.assertEqual(self.client.post(LOGOUT).status_code, status.HTTP_403_FORBIDDEN)


class MeTests(CookieAuthTestCase):
    def test_returns_user_from_cookie(self):
        self.log_in()
        response = self.client.get(ME)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], self.user.email)

    def test_returns_user_from_bearer_header(self):
        access = str(RefreshToken.for_user(self.user).access_token)
        response = APIClient().get(ME, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.json()["email"], self.user.email)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(ME).status_code, status.HTTP_401_UNAUTHORIZED)


class CookieAuthOnApiTests(CookieAuthTestCase):
    """CookieJWTAuthentication is the default for the whole API."""

    def test_safe_request_with_cookie_needs_no_csrf_token(self):
        self.log_in()
        self.assertEqual(self.client.get(STUDENTS).status_code, status.HTTP_200_OK)

    def test_unsafe_request_with_cookie_needs_csrf_token(self):
        self.log_in()
        response = self.client.post(STUDENTS, {"first_name": "New", "last_name": "Student"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Student.objects.exists())

    def test_unsafe_request_with_cookie_and_csrf_token_succeeds(self):
        token = self.log_in()
        response = self.client.post(
            STUDENTS, {"first_name": "New", "last_name": "Student"}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bearer_header_needs_no_csrf_token(self):
        access = str(RefreshToken.for_user(self.user).access_token)
        response = self.client.post(
            STUDENTS, {"first_name": "New", "last_name": "Student"}, format="json", HTTP_AUTHORIZATION=f"Bearer {access}"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_cookie_is_unauthorized(self):
        self.client.cookies["access_token"] = "not-a-token"
        self.assertEqual(self.client.get(STUDENTS).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cookie_for_inactive_user_is_unauthorized(self):
        self.log_in()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(STUDENTS).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_cookie_alone_does_not_authenticate(self):
        self.log_in()
        del self.client.cookies["access_token"]
        self.assertEqual(self.client.get(STUDENTS).status_code, status.HTTP_401_UNAUTHORIZED)


class SchemaDocsTests(CookieAuthTestCase):
    def test_schema_and_docs_require_authentication(self):
        self.assertEqual(self.client.get("/api/v1/schema").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get("/api/v1/docs").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_signed_in_user_can_read_schema_and_docs(self):
        self.log_in()
        schema = self.client.get("/api/v1/schema", HTTP_ACCEPT="application/vnd.oai.openapi+json")
        self.assertEqual(schema.status_code, status.HTTP_200_OK)
        security_schemes = schema.json()["components"]["securitySchemes"]
        self.assertEqual(set(security_schemes), {"jwtAuth", "cookieAuth"})
        self.assertIn("/api/v1/auth/cookie/login", schema.json()["paths"])

        docs = self.client.get("/api/v1/docs")
        self.assertEqual(docs.status_code, status.HTTP_200_OK)
        self.assertNotContains(docs, "cdn.jsdelivr.net")
