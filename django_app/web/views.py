"""The pages Django still renders itself: the public homepage and privacy
policy (Google's OAuth consent screen links to both, so they must work without
signing in), plus redirects from the old server-rendered app's URLs to the
React app at /app/."""

from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_safe
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from accounts.models import User


def _is_active_user(token) -> bool:
    return User.objects.filter(id=token["user_id"], is_active=True).exists()


def _signed_in(request) -> bool:
    """Whether the auth cookies belong to an active account.

    Only checks them: refreshing an expired access token is left to the React
    app, which does it on its first API call.
    """
    for cookie, token_class in ((ACCESS_COOKIE, AccessToken), (REFRESH_COOKIE, RefreshToken)):
        raw = request.COOKIES.get(cookie)
        if not raw:
            continue
        try:
            # Verifies the signature and expiry, and that a refresh token isn't blacklisted.
            if _is_active_user(token_class(raw)):
                return True
        except (TokenError, KeyError):
            continue
    return False


@require_GET
def home_view(request):
    """Public landing page. Signed-in users go straight to the app."""
    if _signed_in(request):
        return redirect("/app/")
    return render(request, "public/home.html")


@require_GET
def privacy_view(request):
    """Public privacy policy, linked from Google's OAuth consent screen."""
    return render(request, "public/privacy.html", {"contact_email": settings.CONTACT_EMAIL})


# Old URL → its React page. Anything under these paths (a student's page, say)
# keeps the rest of its path: /students/<id> → /app/students/<id>.
_MOVED = {
    "login": "login",
    "dashboard": "",
    "analytics": "analytics",
    "assistant": "assistant",
    "students": "students",
    "sessions": "sessions",
    "calendar/create": "sessions/schedule",
    "calendar/connect": "connections",
    "calendar": "sessions",
    "payees": "payees",
    "payments": "payments",
    "connections": "connections",
    "profile": "profile",
    "data": "data",
    "setup": "setup",
}

# Longest first, so calendar/create wins over calendar.
MOVED_PREFIXES = sorted(_MOVED, key=len, reverse=True)


@require_safe
def moved_to_app(request, prefix: str, rest: str = ""):
    """Bookmarks and links to the old pages land on the same page in the React app.

    Temporary (302), so browsers don't cache it forever should the app move again.
    """
    target = "/app/" + "/".join(part for part in (_MOVED[prefix], rest) if part)
    if request.META.get("QUERY_STRING"):
        target += "?" + request.META["QUERY_STRING"]
    return redirect(target)
