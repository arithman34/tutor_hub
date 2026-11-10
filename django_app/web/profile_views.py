from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User, UserRole

from .auth import login_required


@login_required
def profile_page(request):
    return render(
        request,
        "profile/index.html",
        {
            "user": request.user,
            "active_page": "profile",
            "success": request.GET.get("success", ""),
            "error": request.GET.get("error", ""),
        },
    )


@login_required
@require_http_methods(["POST"])
def profile_update(request):
    user = request.user
    email = request.POST.get("email", "")

    if email != user.email and User.objects.filter(email=email).exists():
        return redirect("/profile?error=email_taken")

    role = request.POST.get("role", "")
    if user.is_admin and role in (UserRole.ADMIN, UserRole.ADMIN_TUTOR):
        user.role = role

    user.email = email
    user.first_name = request.POST.get("first_name", "")
    user.last_name = request.POST.get("last_name", "")
    user.address = request.POST.get("address", "").strip() or None
    user.save()

    return redirect("/profile?success=details")


@login_required
@require_http_methods(["POST"])
def profile_password(request):
    user = request.user
    current_password = request.POST.get("current_password", "")
    new_password = request.POST.get("new_password", "")
    confirm_password = request.POST.get("confirm_password", "")

    if not user.check_password(current_password):
        return redirect("/profile?error=wrong_password")
    if new_password != confirm_password:
        return redirect("/profile?error=password_mismatch")

    user.set_password(new_password)
    user.save()
    return redirect("/profile?success=password")
