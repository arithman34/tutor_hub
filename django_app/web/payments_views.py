import uuid
from datetime import datetime, timezone

from django.db.models import Q
from django.shortcuts import redirect, render

from billing.models import Payee, Payment

from .auth import login_required


@login_required
def payments_index(request):
    """GET lists payments, POST creates one — matches the single `/payments`
    path the original FastAPI router and `new.html`'s form both use."""
    if request.method == "POST":
        return payments_create(request)
    return payments_list(request)


def payments_list(request):
    user = request.user
    if not user.is_admin:
        return redirect("/dashboard")

    q = request.GET.get("q", "")
    qs = Payment.objects.select_related("payee", "user").order_by("-payment_date")
    if q:
        qs = qs.filter(Q(payee__first_name__icontains=q) | Q(payee__last_name__icontains=q))
    payments = qs[:20]

    return render(request, "payments/index.html", {"user": user, "active_page": "payments", "payments": payments, "q": q})


@login_required
def payments_new(request):
    if not request.user.is_admin:
        return redirect("/dashboard")

    payees = Payee.objects.order_by("first_name")
    return render(
        request,
        "payments/new.html",
        {
            "user": request.user,
            "active_page": "payments",
            "payees": payees,
            "selected_payee_id": request.GET.get("payee_id", ""),
        },
    )


def payments_create(request):
    user = request.user
    if not user.is_admin:
        return redirect("/dashboard")

    payment_date = datetime.strptime(request.POST["payment_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    Payment.objects.create(
        user=user,
        payee_id=uuid.UUID(request.POST["payee_id"]),
        amount=request.POST["amount"],
        payment_date=payment_date,
        payment_reference=request.POST.get("payment_reference") or None,
    )
    return redirect("/payments")
