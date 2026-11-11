from datetime import datetime, timedelta, timezone

from django.db.models import Sum

from accounts.models import User
from billing.models import Payee, Payment
from billing.services import payee_balances
from students.models import Student
from tutoring_sessions.models import Session


def _pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def _total_hours(**kwargs) -> float:
    minutes = 0.0
    for start, end in Session.objects.filter(**kwargs).values_list("session_start_time", "session_end_time"):
        minutes += (end - start).total_seconds() / 60
    return minutes / 60


def get_dashboard_stats(user: User) -> dict:
    """Headline numbers for the account's own tutoring business."""
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        last_month_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        last_month_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    def sum_payments(**kwargs) -> float:
        return float(Payment.objects.filter(user=user, **kwargs).aggregate(total=Sum("amount"))["total"] or 0)

    revenue_this_month = sum_payments(payment_date__gte=this_month_start)
    revenue_last_month = sum_payments(payment_date__gte=last_month_start, payment_date__lt=last_month_end)

    sessions_this_month = Session.objects.filter(user=user, session_date__gte=this_month_start, session_date__lte=now).count()
    sessions_last_month = Session.objects.filter(user=user, session_date__gte=last_month_start, session_date__lt=last_month_end).count()

    hours_this_month = _total_hours(user=user, session_date__gte=this_month_start, session_date__lte=now)
    hours_last_month = _total_hours(user=user, session_date__gte=last_month_start, session_date__lt=last_month_end)

    balances = payee_balances(Payee.objects.filter(user=user))
    owing = [balance for balance in balances.values() if balance < 0]

    return {
        "revenue_alltime": sum_payments(),
        "revenue_this_month": revenue_this_month,
        "revenue_this_year": sum_payments(payment_date__gte=this_year_start),
        "mom_trend": _pct_change(revenue_this_month, revenue_last_month),
        "outstanding_total": round(-sum(owing), 2),
        "outstanding_payees": len(owing),
        "active_students": Student.objects.filter(user=user, is_active=True).count(),
        "sessions_this_week": Session.objects.filter(user=user, session_date__gte=week_start, session_date__lte=now).count(),
        "sessions_this_month": sessions_this_month,
        "sessions_pct_change": _pct_change(sessions_this_month, sessions_last_month),
        "hours_this_month": round(hours_this_month, 1),
        "hours_pct_change": _pct_change(hours_this_month, hours_last_month),
    }
