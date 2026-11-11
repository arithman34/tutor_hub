from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User


def _has_users() -> bool:
    return User.objects.exists()


def setup_index(request):
    """GET shows the first-run form, POST creates the first account — matches
    the single `/setup` path the original FastAPI router and the template's
    form action both use. No auth is required: this page only does
    anything while the `users` table is empty."""
    if request.method == "POST":
        return setup_submit(request)
    return setup_page(request)


def setup_page(request):
    if _has_users():
        return redirect("/login")
    return render(request, "setup/index.html", {})


@require_http_methods(["POST"])
def setup_submit(request):
    if _has_users():
        return redirect("/login")

    User.objects.create_user(
        email=request.POST.get("email", ""),
        password=request.POST.get("password", ""),
        first_name=request.POST.get("first_name", "").strip().title(),
        last_name=request.POST.get("last_name", "").strip().title(),
        is_active=True,
    )
    return redirect("/login")
