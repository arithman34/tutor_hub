"""Cookie-based web authentication, reusing the same JWTs the API issues.

The FastAPI app's web routes and JSON API shared one auth system (JWT
access/refresh tokens), just carried over different transports — an
Authorization header for API clients, httponly cookies for browser pages.
This mirrors that instead of inventing a second, session-based auth system
alongside SimpleJWT.
"""

from functools import wraps

from django.conf import settings
from django.shortcuts import redirect
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.cookies import ACCESS_COOKIE, REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies  # noqa: F401
from accounts.models import User


def _user_from_access_token(raw_token: str) -> User | None:
    try:
        token = AccessToken(raw_token)
        user = User.objects.get(id=token["user_id"])
    except (TokenError, User.DoesNotExist, KeyError):
        return None
    return user if user.is_active else None


def get_current_user(request):
    """Returns (user, refreshed_tokens). refreshed_tokens is (access, refresh)
    when the refresh-token path minted new tokens that the caller should set
    as cookies on the response, else None."""
    access_token = request.COOKIES.get(ACCESS_COOKIE)
    if access_token:
        user = _user_from_access_token(access_token)
        if user:
            return user, None

    refresh_token = request.COOKIES.get(REFRESH_COOKIE)
    if not refresh_token:
        return None, None

    try:
        old_refresh = RefreshToken(refresh_token)
        user = User.objects.get(id=old_refresh["user_id"])
    except (TokenError, User.DoesNotExist, KeyError):
        return None, None

    if not user.is_active:
        return None, None

    if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"):
        try:
            old_refresh.blacklist()
        except AttributeError:
            pass

    new_refresh = RefreshToken.for_user(user)
    return user, (str(new_refresh.access_token), str(new_refresh))


def login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user, refreshed = get_current_user(request)
        if user is None:
            return redirect("/login")
        request.user = user
        response = view(request, *args, **kwargs)
        if refreshed:
            set_auth_cookies(response, *refreshed)
        return response

    return wrapped

