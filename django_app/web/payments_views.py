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
    q = request.GET.get("q", "")
    qs = Payment.objects.filter(user=user).select_related("payee").order_by("-payment_date")
    if q:
        qs = qs.filter(Q(payee__first_name__icontains=q) | Q(payee__last_name__icontains=q))
    payments = qs[:20]

    return render(request, "payments/index.html", {"user": user, "active_page": "payments", "payments": payments, "q": q})


@login_required
def payments_new(request):
    payees = Payee.objects.filter(user=request.user).order_by("first_name")
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
    try:
        payee = Payee.objects.get(id=uuid.UUID(request.POST.get("payee_id", "")), user=user)
    except (Payee.DoesNotExist, ValueError):
        return redirect("/payments/new")

    payment_date = datetime.strptime(request.POST["payment_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    Payment.objects.create(
        user=user,
        payee=payee,
        amount=request.POST["amount"],
        payment_date=payment_date,
        payment_reference=request.POST.get("payment_reference") or None,
    )
    return redirect("/payments")
