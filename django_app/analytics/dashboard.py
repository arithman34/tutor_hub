"""Numbers for the dashboard page.

Payments are real instants. Session times are wall-clock times labelled UTC
(see zoom_integration.services.to_wall_clock), so "now" for sessions is the
local time, labelled UTC, before it's compared with them.
"""

import calendar
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from django.db.models import Sum

from accounts.models import User
from billing.models import Payee, Payment
from billing.services import payee_balances
from students.models import Student
from tutoring_sessions.models import Session
from zoom_integration.services import to_wall_clock

from .services import _months_back, pct_change, step_bucket

REVENUE_MONTHS = 12
UPCOMING_DEFAULT_DAYS = 4  # Today and the next three days.
UPCOMING_LIMIT = 12


def _month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def same_period_last_month(now: datetime) -> tuple[datetime, datetime]:
    """The start and (exclusive) end of last month's days 1..today.

    On 13 Nov that's 1 Oct to the start of 14 Oct. Clamped to last month's
    length, so 31 March compares with the whole of February.
    """
    start = _months_back(now, 1)
    days_in_last_month = calendar.monthrange(start.year, start.month)[1]
    end = start + timedelta(days=min(now.day, days_in_last_month))
    return start, end


def _hours(sessions) -> float:
    return sum((end - start).total_seconds() for start, end in sessions.values_list("session_start_time", "session_end_time")) / 3600


def _revenue(user: User, **filters) -> float:
    return float(Payment.objects.filter(user=user, **filters).aggregate(total=Sum("amount"))["total"] or 0)


def get_dashboard_stats(user: User, now: datetime | None = None) -> dict:
    """Headline numbers for the account's own tutoring business.

    Month-on-month changes compare month-to-date with the same days of last
    month, so they don't read as a big drop early in the month.
    """
    now = now or datetime.now(timezone.utc)
    wall_now = to_wall_clock(now)

    month_start = _month_start(now)
    compare_start, compare_end = same_period_last_month(now)
    year_start = month_start.replace(month=1)

    revenue_this_month = _revenue(user, payment_date__gte=month_start, payment_date__lte=now)
    revenue_same_period = _revenue(user, payment_date__gte=compare_start, payment_date__lt=compare_end)
    revenue_last_month = _revenue(user, payment_date__gte=compare_start, payment_date__lt=month_start)
    revenue_this_year = _revenue(user, payment_date__gte=year_start, payment_date__lte=now)

    # Assume the rest of this month brings in what the rest of last month did.
    # Payments arrive in lumps (a parent paying for the month), which a simple
    # pace-based projection would wildly over- or under-estimate.
    revenue_projected = round(revenue_this_month + (revenue_last_month - revenue_same_period), 2) if revenue_last_month else None

    sessions = Session.objects.filter(user=user)
    wall_month_start = _month_start(wall_now)
    wall_compare_start, wall_compare_end = same_period_last_month(wall_now)
    sessions_mtd = sessions.filter(session_date__gte=wall_month_start, session_date__lte=wall_now)
    sessions_last_mtd = sessions.filter(session_date__gte=wall_compare_start, session_date__lt=wall_compare_end)
    sessions_week = sessions.filter(session_date__gt=wall_now - timedelta(days=7), session_date__lte=wall_now)
    sessions_prev_week = sessions.filter(session_date__gt=wall_now - timedelta(days=14), session_date__lte=wall_now - timedelta(days=7))
    sessions_this_year = sessions.filter(session_date__gte=wall_month_start.replace(month=1), session_date__lte=wall_now)

    hours_this_month = _hours(sessions_mtd)
    hours_this_year = _hours(sessions_this_year)
    sessions_this_month = sessions_mtd.count()
    sessions_this_week = sessions_week.count()

    balances = payee_balances(Payee.objects.filter(user=user))
    owing = [balance for balance in balances.values() if balance < 0]

    # Running total for each day of this month so far, for the sparkline.
    by_day = defaultdict(float)
    for paid_at, amount in Payment.objects.filter(user=user, payment_date__gte=month_start, payment_date__lte=now).values_list(
        "payment_date", "amount"
    ):
        by_day[paid_at.day] += float(amount)
    cumulative, running = [], 0.0
    for day in range(1, now.day + 1):
        running += by_day[day]
        cumulative.append(round(running, 2))

    return {
        "revenue_alltime": _revenue(user, payment_date__lte=now),
        "revenue_this_month": revenue_this_month,
        "revenue_this_year": revenue_this_year,
        "revenue_same_period_last_month": revenue_same_period,
        "revenue_projected": revenue_projected,
        "revenue_month_to_date": cumulative,
        "mom_trend": pct_change(revenue_this_month, revenue_same_period),
        "compare_from": compare_start.date(),
        "compare_to": (compare_end - timedelta(days=1)).date(),
        "outstanding_total": round(-sum(owing), 2),
        "outstanding_payees": len(owing),
        "average_hourly_rate": round(revenue_this_year / hours_this_year, 2) if hours_this_year else None,
        "hours_this_year": round(hours_this_year, 1),
        "active_students": Student.objects.filter(user=user, is_active=True).count(),
        "students_taught_this_month": sessions_mtd.values("student_id").distinct().count(),
        "sessions_this_week": sessions_this_week,
        "sessions_week_pct_change": pct_change(sessions_this_week, sessions_prev_week.count()),
        "sessions_this_month": sessions_this_month,
        "sessions_pct_change": pct_change(sessions_this_month, sessions_last_mtd.count()),
        "hours_this_month": round(hours_this_month, 1),
        "hours_pct_change": pct_change(hours_this_month, _hours(sessions_last_mtd)),
    }


def get_revenue_by_month(user: User, now: datetime | None = None) -> list[dict]:
    """Payments received in each of the last 12 months, oldest first.

    The last entry is the current month, flagged in progress.
    """
    now = now or datetime.now(timezone.utc)
    first = _months_back(now, REVENUE_MONTHS - 1)
    totals = defaultdict(float)
    for paid_at, amount in Payment.objects.filter(user=user, payment_date__gte=first, payment_date__lte=now).values_list(
        "payment_date", "amount"
    ):
        totals[(paid_at.year, paid_at.month)] += float(amount)

    months, current = [], first
    for _ in range(REVENUE_MONTHS):
        months.append(
            {
                "month": current.date(),
                "revenue": round(totals[(current.year, current.month)], 2),
                "in_progress": (current.year, current.month) == (now.year, now.month),
            }
        )
        current = step_bucket(current, "month")
    return months


def get_upcoming_sessions(user: User, days: int = UPCOMING_DEFAULT_DAYS, now: datetime | None = None) -> list[dict]:
    """Sessions from now until the end of the `days`th day (today is day 1)."""
    wall_now = to_wall_clock(now or datetime.now(timezone.utc))
    until = _day_start(wall_now) + timedelta(days=days)
    sessions = (
        Session.objects.filter(user=user, session_end_time__gt=wall_now, session_start_time__lt=until)
        .select_related("student")
        .order_by("session_start_time")[:UPCOMING_LIMIT]
    )
    return [
        {
            "id": session.id,
            "student_id": session.student_id,
            "student_name": str(session.student),
            "level": session.student.level,
            "topic_tags": session.topic_tags or None,
            "start": session.session_start_time,
            "end": session.session_end_time,
        }
        for session in sessions
    ]


def get_student_breakdown(user: User, now: datetime | None = None) -> list[dict]:
    """Each student taught this month so far, with hours and what they were billed.

    Billed revenue is hours times the student's hourly rate, the same sum the
    payee balances use. Payments are per payee, not per student, so this is
    the only per-student revenue there is. Most revenue first.
    """
    wall_now = to_wall_clock(now or datetime.now(timezone.utc))
    rows = Session.objects.filter(user=user, session_date__gte=_month_start(wall_now), session_date__lte=wall_now).values_list(
        "student_id", "student__first_name", "student__last_name", "student__hourly_rate", "session_start_time", "session_end_time"
    )
    students: dict = {}
    for student_id, first_name, last_name, hourly_rate, start, end in rows:
        row = students.setdefault(
            student_id,
            {"student_id": student_id, "student_name": f"{first_name} {last_name}", "sessions": 0, "hours": 0.0, "revenue": 0.0, "hourly_rate": hourly_rate},
        )
        hours = (end - start).total_seconds() / 3600
        row["sessions"] += 1
        row["hours"] += hours
        row["revenue"] += hours * (hourly_rate or 0)

    for row in students.values():
        row["hours"] = round(row["hours"], 2)
        row["revenue"] = round(row["revenue"], 2)
    return sorted(students.values(), key=lambda row: (-row["revenue"], -row["hours"], row["student_name"]))
