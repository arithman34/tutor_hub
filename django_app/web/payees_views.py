from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from billing.models import Payee, Payment
from billing.views import payee_balance

from .auth import login_required


@login_required
def payees_index(request):
    """GET lists payees, POST creates one — matches the single `/payees`
    path the original FastAPI router and `new.html`'s form both use."""
    if request.method == "POST":
        return payees_create(request)
    return payees_list(request)


def payees_list(request):
    user = request.user
    if not user.is_admin:
        return redirect("/dashboard")

    q = request.GET.get("q", "")
    qs = Payee.objects.select_related("user").order_by("first_name")
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
    payees = list(qs)
    balances = {str(p.id): payee_balance(p) for p in payees}

    return render(
        request,
        "payees/index.html",
        {"user": user, "active_page": "payees", "payees": payees, "q": q, "balances": balances},
    )


@login_required
def payees_new(request):
    if not request.user.is_admin:
        return redirect("/dashboard")
    return render(request, "payees/new.html", {"user": request.user, "active_page": "payees"})


def payees_create(request):
    user = request.user
    if not user.is_admin:
        return redirect("/dashboard")

    Payee.objects.create(
        user=user,
        first_name=request.POST.get("first_name", "").strip().title(),
        last_name=request.POST.get("last_name", "").strip().title(),
        email=request.POST.get("email") or None,
        phone_number=request.POST.get("phone_number") or None,
        bank_reference_pattern=request.POST.get("bank_reference_pattern") or None,
    )
    return redirect("/payees")


@login_required
def payee_detail(request, payee_id):
    user = request.user
    if not user.is_admin:
        return redirect("/dashboard")

    try:
        payee = Payee.objects.prefetch_related("students").get(id=payee_id)
    except (Payee.DoesNotExist, ValueError, TypeError):
        return redirect("/payees")

    balance = payee_balance(payee)
    payments = Payment.objects.filter(payee_id=payee_id).order_by("-payment_date")

    return render(
        request,
        "payees/detail.html",
        {"user": user, "active_page": "payees", "payee": payee, "balance": balance, "payments": payments},
    )


@login_required
@require_http_methods(["POST"])
def payee_update(request, payee_id):
    if not request.user.is_admin:
        return redirect("/dashboard")

    payee = get_object_or_404(Payee, id=payee_id)

    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    if first_name:
        payee.first_name = first_name.title()
    if last_name:
        payee.last_name = last_name.title()
    payee.email = request.POST.get("email") or None
    payee.phone_number = request.POST.get("phone_number") or None
    payee.bank_reference_pattern = request.POST.get("bank_reference_pattern") or None
    payee.save()

    return redirect(f"/payees/{payee_id}")
