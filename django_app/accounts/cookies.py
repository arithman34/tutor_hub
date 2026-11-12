"""The httponly cookies that carry TutorHub's JWTs in a browser.

Both the server-rendered pages (web/) and the browser API (the cookie
endpoints in accounts.views, read by accounts.authentication) use these, so
there is one sign-in no matter which side of the app a request comes from.
"""

from django.conf import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

ACCESS_COOKIE_MAX_AGE = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
REFRESH_COOKIE_MAX_AGE = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_auth_cookies(response, access_token: str, refresh_token: str):
    options = {"httponly": True, "samesite": "Lax", "secure": settings.SECURE_COOKIES}
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=ACCESS_COOKIE_MAX_AGE, **options)
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=REFRESH_COOKIE_MAX_AGE, **options)


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, samesite="Lax")
    response.delete_cookie(REFRESH_COOKIE, samesite="Lax")
