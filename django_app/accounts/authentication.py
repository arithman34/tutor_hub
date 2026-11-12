"""DRF authentication that accepts a JWT from a header or a cookie.

API clients send `Authorization: Bearer <token>`, as before. The browser
app instead relies on the httponly access_token cookie (see cookies.py), so
JavaScript never handles the token itself.

Cookies are sent automatically, including on requests another site causes
the browser to make, so cookie-authenticated requests must pass Django's
CSRF check. Header-authenticated requests don't need it, since a browser
never adds an Authorization header on its own.
"""

from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication

from .cookies import ACCESS_COOKIE


def enforce_csrf(request):
    """Run Django's CSRF check on a DRF request, as SessionAuthentication does.

    Safe methods (GET, HEAD, OPTIONS, TRACE) always pass.
    """
    check = CSRFCheck(lambda _request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        enforce_csrf(request)
        return user, validated_token
