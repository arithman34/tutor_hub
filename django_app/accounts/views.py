"""Auth endpoints for the browser app.

The token endpoints in urls.py (login/refresh/logout) return JWTs in the
response body for API clients. These cookie variants keep the tokens in
httponly cookies instead, so the browser app's JavaScript never sees them.

Every state-changing call here is CSRF-checked. A browser client gets the
token from GET /csrf first, then sends it back in the X-CSRFToken header.
Even login is checked, so another site can't sign a visitor into an account
it controls ("login CSRF").

These views opt out of authentication (see _PublicAuthView): a stale
access cookie would otherwise make DRF reject the request with 401 before a
user ever got the chance to log in again or refresh.
"""

from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import enforce_csrf
from .cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from .serializers import UserSerializer

class _PublicAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        # With no authentication classes DRF has no WWW-Authenticate value and
        # turns 401s into 403s. Keep 401 for bad credentials or tokens, so a
        # client can tell "log in again" (401) from "CSRF failed" (403).
        return 'Bearer realm="api"'


_CsrfTokenSerializer = inline_serializer("CsrfToken", {"csrf_token": serializers.CharField()})
_CookieLoginSerializer = inline_serializer(
    "CookieLogin", {"email": serializers.EmailField(), "password": serializers.CharField()}
)


class CsrfView(_PublicAuthView):

    @extend_schema(
        summary="Get a CSRF token",
        description="Sets the csrftoken cookie and returns the same token. Send it as the X-CSRFToken header on cookie-authenticated POST, PUT, PATCH and DELETE requests.",
        responses=_CsrfTokenSerializer,
    )
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class CookieLoginView(_PublicAuthView):

    @extend_schema(
        summary="Log in with httponly cookies",
        request=_CookieLoginSerializer,
        responses={200: UserSerializer},
    )
    def post(self, request):
        enforce_csrf(request)
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response = Response(UserSerializer(serializer.user).data)
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data["refresh"])
        return response


class CookieRefreshView(_PublicAuthView):

    @extend_schema(
        summary="Refresh the cookie tokens",
        description="Swaps the refresh_token cookie for a new access/refresh pair. Call it after a 401, then retry the request.",
        request=None,
        responses={204: None},
    )
    def post(self, request):
        enforce_csrf(request)
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not raw_refresh:
            raise exceptions.NotAuthenticated("No refresh token cookie.")

        serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, exceptions.APIException):
            response = Response({"detail": "Refresh token is invalid or expired."}, status=status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response)
            return response

        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data["refresh"])
        return response


class CookieLogoutView(_PublicAuthView):

    @extend_schema(summary="Log out and clear the cookies", request=None, responses={204: None})
    def post(self, request):
        enforce_csrf(request)
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    @extend_schema(summary="The signed-in user", responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
