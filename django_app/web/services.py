from datetime import datetime, timedelta, timezone

from django.db.models import Sum

from accounts.models import PayoutType, User, UserRole
from billing.models import Payment
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


def get_tutor_stats(user: User) -> dict:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    active_students = Student.objects.filter(user=user, is_active=True).count()
    total_hours = _total_hours(user=user)
    amount_owed = round(total_hours * (user.payout_hourly_rate or 0), 2)
    sessions_this_month = Session.objects.filter(user=user, session_date__gte=month_start, session_date__lte=now).count()
    sessions_this_week = Session.objects.filter(user=user, session_date__gte=week_start, session_date__lte=now).count()

    return {
        "active_students": active_students,
        "sessions_this_week": sessions_this_week,
        "sessions_this_month": sessions_this_month,
        "amount_owed": amount_owed,
    }


def get_admin_stats() -> dict:
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        last_month_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        last_month_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    def sum_payments(**kwargs) -> float:
        return float(Payment.objects.filter(**kwargs).aggregate(total=Sum("amount"))["total"] or 0)

    revenue_alltime = sum_payments()
    revenue_this_month = sum_payments(payment_date__gte=this_month_start)
    revenue_last_month = sum_payments(payment_date__gte=last_month_start, payment_date__lt=last_month_end)
    revenue_this_year = sum_payments(payment_date__gte=this_year_start)

    hourly_obligations = 0.0
    for tutor in User.objects.filter(role=UserRole.TUTOR, payout_type=PayoutType.HOURLY):
        hours = _total_hours(user=tutor, session_date__gte=this_month_start)
        hourly_obligations += hours * float(tutor.payout_hourly_rate or 0)

    pct_rates = User.objects.filter(role=UserRole.TUTOR, payout_type=PayoutType.PERCENTAGE, is_active=True).values_list(
        "payout_percentage", flat=True
    )
    percentage_obligations = sum(float(p or 0) / 100 * revenue_this_month for p in pct_rates)

    total_payout_obligations = round(hourly_obligations + percentage_obligations, 2)
    profit_margin = round(revenue_this_month - total_payout_obligations, 2)
    mom_trend = _pct_change(revenue_this_month, revenue_last_month)

    sessions_this_month = Session.objects.filter(session_date__gte=this_month_start, session_date__lte=now).count()
    sessions_last_month = Session.objects.filter(session_date__gte=last_month_start, session_date__lt=last_month_end).count()
    sessions_pct_change = _pct_change(sessions_this_month, sessions_last_month)

    hours_this_month_raw = _total_hours(session_date__gte=this_month_start, session_date__lte=now)
    hours_last_month_raw = _total_hours(session_date__gte=last_month_start, session_date__lt=last_month_end)
    hours_pct_change = _pct_change(hours_this_month_raw, hours_last_month_raw)

    total_past = Session.objects.filter(session_date__lte=now).count()
    completion_rate = 100.0 if total_past else 0

    return {
        "revenue_alltime": revenue_alltime,
        "revenue_this_month": revenue_this_month,
        "revenue_this_year": revenue_this_year,
        "total_payout_obligations": total_payout_obligations,
        "profit_margin": profit_margin,
        "mom_trend": mom_trend,
        "sessions_this_month": sessions_this_month,
        "sessions_pct_change": sessions_pct_change,
        "hours_this_month": round(hours_this_month_raw, 1),
        "hours_pct_change": hours_pct_change,
        "completion_rate": completion_rate,
    }
