from django.urls import path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views

urlpatterns = [
    # Tokens in the response body, for API clients.
    path("login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout", TokenBlacklistView.as_view(), name="token_blacklist"),
    # Tokens in httponly cookies, for the browser app.
    path("csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("cookie/login", views.CookieLoginView.as_view(), name="auth-cookie-login"),
    path("cookie/refresh", views.CookieRefreshView.as_view(), name="auth-cookie-refresh"),
    path("cookie/logout", views.CookieLogoutView.as_view(), name="auth-cookie-logout"),
    path("me", views.MeView.as_view(), name="auth-me"),
]
