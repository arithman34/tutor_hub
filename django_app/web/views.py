from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

from . import services
from .auth import clear_auth_cookies, login_required, set_auth_cookies


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == "GET":
        return render(request, "auth/login.html")

    email = request.POST.get("email", "")
    password = request.POST.get("password", "")
    user = User.objects.filter(email=email).first()

    if not user or not user.check_password(password) or not user.is_active:
        return render(request, "auth/login.html", {"error": "Invalid email or password"}, status=400)

    refresh = RefreshToken.for_user(user)
    response = redirect("/dashboard")
    set_auth_cookies(response, str(refresh.access_token), str(refresh))
    return response


@require_http_methods(["POST"])
def logout_view(request):
    refresh_token = request.COOKIES.get("refresh_token")
    if refresh_token:
        try:
            RefreshToken(refresh_token).blacklist()
        except (TokenError, AttributeError):
            pass

    response = redirect("/login")
    clear_auth_cookies(response)
    return response


@login_required
def dashboard_view(request):
    user = request.user
    stats = services.get_admin_stats() if user.is_admin else services.get_tutor_stats(user)
    return render(request, "dashboard/index.html", {"user": user, "active_page": "dashboard", **stats})
