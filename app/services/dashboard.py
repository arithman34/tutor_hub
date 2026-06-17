from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import PayoutType, User, UserRole

_mins = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 60
_s_hours = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 3600


def _pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


async def get_tutor_stats(db: AsyncSession, user: User) -> dict:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    active_students = await db.scalar(select(func.count()).select_from(Student).where(Student.user_id == user.id, Student.is_active)) or 0
    total_minutes = float(await db.scalar(select(func.sum(_mins)).where(Session.user_id == user.id)) or 0)
    amount_owed = round((total_minutes / 60) * (user.payout_hourly_rate or 0), 2)
    sessions_this_month = (
        await db.scalar(
            select(func.count())
            .select_from(Session)
            .where(Session.user_id == user.id, Session.session_date >= month_start, Session.session_date <= now)
        )
        or 0
    )
    sessions_this_week = (
        await db.scalar(
            select(func.count())
            .select_from(Session)
            .where(Session.user_id == user.id, Session.session_date >= week_start, Session.session_date <= now)
        )
        or 0
    )

    return {
        "active_students": active_students,
        "sessions_this_week": sessions_this_week,
        "sessions_this_month": sessions_this_month,
        "amount_owed": amount_owed,
    }


async def get_admin_stats(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        last_month_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        last_month_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    four_weeks_ago = now - timedelta(weeks=4)

    revenue_alltime = float(await db.scalar(select(func.sum(Payment.amount))) or 0)
    revenue_this_month = float(await db.scalar(select(func.sum(Payment.amount)).where(Payment.payment_date >= this_month_start)) or 0)
    revenue_last_month = float(
        await db.scalar(select(func.sum(Payment.amount)).where(Payment.payment_date >= last_month_start, Payment.payment_date < last_month_end)) or 0
    )
    revenue_this_year = float(await db.scalar(select(func.sum(Payment.amount)).where(Payment.payment_date >= this_year_start)) or 0)

    hourly_rows = (
        await db.execute(
            select(User.payout_hourly_rate, func.sum(_mins).label("mins"))
            .join(Session, Session.user_id == User.id)
            .where(User.role == UserRole.tutor, User.payout_type == PayoutType.hourly, Session.session_date >= this_month_start)
            .group_by(User.id, User.payout_hourly_rate)
        )
    ).all()
    hourly_obligations = sum(float(r.mins or 0) / 60 * float(r.payout_hourly_rate or 0) for r in hourly_rows)

    pct_rates = (
        (
            await db.execute(
                select(User.payout_percentage).where(User.role == UserRole.tutor, User.payout_type == PayoutType.percentage, User.is_active)
            )
        )
        .scalars()
        .all()
    )
    percentage_obligations = sum(float(p or 0) / 100 * revenue_this_month for p in pct_rates)

    total_payout_obligations = round(hourly_obligations + percentage_obligations, 2)
    profit_margin = round(revenue_this_month - total_payout_obligations, 2)
    mom_trend = _pct_change(revenue_this_month, revenue_last_month)

    active_tutors = await db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.tutor, User.is_active)) or 0
    active_students = await db.scalar(select(func.count()).select_from(Student).where(Student.is_active)) or 0

    sessions_this_month = (
        await db.scalar(select(func.count()).select_from(Session).where(Session.session_date >= this_month_start, Session.session_date <= now)) or 0
    )
    sessions_last_month = (
        await db.scalar(
            select(func.count()).select_from(Session).where(Session.session_date >= last_month_start, Session.session_date < last_month_end)
        )
        or 0
    )
    sessions_pct_change = _pct_change(sessions_this_month, sessions_last_month)

    hours_this_month_raw = (
        float(await db.scalar(select(func.sum(_mins)).where(Session.session_date >= this_month_start, Session.session_date <= now)) or 0) / 60
    )
    hours_last_month_raw = (
        float(await db.scalar(select(func.sum(_mins)).where(Session.session_date >= last_month_start, Session.session_date < last_month_end)) or 0)
        / 60
    )
    hours_pct_change = _pct_change(hours_this_month_raw, hours_last_month_raw)

    total_past = await db.scalar(select(func.count()).select_from(Session).where(Session.session_date <= now)) or 0
    completion_rate = 100.0 if total_past else 0
    cancellation_rate = 0.0
    avg_students_per_tutor = round(active_students / active_tutors, 1) if active_tutors else 0

    top_by_hours = [
        {"name": f"{r.first_name} {r.last_name}", "hours": round(float(r.mins or 0) / 60, 1)}
        for r in (
            await db.execute(
                select(User.first_name, User.last_name, func.sum(_mins).label("mins"))
                .join(Session, Session.user_id == User.id)
                .where(User.role == UserRole.tutor)
                .group_by(User.id, User.first_name, User.last_name)
                .order_by(func.sum(_mins).desc())
                .limit(5)
            )
        ).all()
    ]

    top_by_revenue = [
        {"name": f"{r.first_name} {r.last_name}", "revenue": round(float(r.rev or 0), 2)}
        for r in (
            await db.execute(
                select(User.first_name, User.last_name, func.sum(_mins / 60.0 * Student.hourly_rate).label("rev"))
                .select_from(User)
                .join(Session, Session.user_id == User.id)
                .join(Student, Session.student_id == Student.id)
                .where(User.role == UserRole.tutor, Student.hourly_rate.isnot(None))
                .group_by(User.id, User.first_name, User.last_name)
                .order_by(func.sum(_mins / 60.0 * Student.hourly_rate).desc())
                .limit(5)
            )
        ).all()
    ]

    tutors_with_recent = select(Session.user_id).where(Session.session_date >= four_weeks_ago).distinct()
    inactive_tutors = (
        (await db.execute(select(User).where(User.role == UserRole.tutor, User.is_active == True, ~User.id.in_(tutors_with_recent)))).scalars().all()
    )

    tutors_with_balance = [
        {
            "name": f"{r.first_name} {r.last_name}",
            "hours": round(float(r.mins or 0) / 60, 1),
            "owed": round(float(r.mins or 0) / 60 * float(r.payout_hourly_rate or 0), 2) if r.payout_type == PayoutType.hourly else None,
        }
        for r in (
            await db.execute(
                select(User.first_name, User.last_name, User.payout_type, User.payout_hourly_rate, func.sum(_mins).label("mins"))
                .join(Session, Session.user_id == User.id)
                .where(User.role == UserRole.tutor)
                .group_by(User.id, User.first_name, User.last_name, User.payout_type, User.payout_hourly_rate)
                .having(func.sum(_mins) > 0)
            )
        ).all()
    ]

    students_with_recent = select(Session.student_id).where(Session.session_date >= four_weeks_ago).distinct()
    at_risk_students = (
        (
            await db.execute(
                select(Student)
                .options(joinedload(Student.user))
                .where(Student.is_active == True, ~Student.id.in_(students_with_recent))
                .order_by(Student.first_name)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    new_students = (
        (
            await db.execute(
                select(Student).options(joinedload(Student.user)).where(Student.created_at >= this_month_start).order_by(Student.created_at.desc())
            )
        )
        .unique()
        .scalars()
        .all()
    )

    students_no_active_tutor = (
        (await db.execute(select(Student).join(User, Student.user_id == User.id).where(Student.is_active == True, User.is_active == False)))
        .scalars()
        .all()
    )

    cost_rows = (
        await db.execute(
            select(Student.payee_id, func.sum(_s_hours * Student.hourly_rate).label("cost"))
            .join(Session, Session.student_id == Student.id)
            .where(Student.payee_id.isnot(None), Student.hourly_rate.isnot(None))
            .group_by(Student.payee_id)
        )
    ).all()
    paid_rows = (await db.execute(select(Payment.payee_id, func.sum(Payment.amount).label("paid")).group_by(Payment.payee_id))).all()
    _cost_map = {str(r.payee_id): float(r.cost or 0) for r in cost_rows}
    _paid_map = {str(r.payee_id): float(r.paid or 0) for r in paid_rows}
    all_payee_ids = set(_cost_map) | set(_paid_map)
    outstanding_balance = round(sum(max(0, _cost_map.get(pid, 0) - _paid_map.get(pid, 0)) for pid in all_payee_ids), 2)

    tutors_no_payout = (await db.execute(select(User).where(User.role == UserRole.tutor, User.is_active, User.payout_type.is_(None)))).scalars().all()

    _cm, _cy = now.month - 11, now.year
    if _cm <= 0:
        _cm += 12
        _cy -= 1
    twelve_months_ago = now.replace(year=_cy, month=_cm, day=1, hour=0, minute=0, second=0, microsecond=0)
    _month_expr = func.date_trunc(_text("'month'"), Student.created_at)
    growth_rows = (
        await db.execute(
            select(_month_expr.label("month"), func.count().label("count")).where(Student.created_at >= twelve_months_ago).group_by(_month_expr)
        )
    ).all()
    _growth_lookup = {row.month.strftime("%Y-%m"): row.count for row in growth_rows}

    students_chart_labels, students_chart_data = [], []
    for i in range(11, -1, -1):
        _m, _y = now.month - i, now.year
        while _m <= 0:
            _m += 12
            _y -= 1
        students_chart_labels.append(f"{_y}-{_m:02d}-01T00:00:00")
        students_chart_data.append(_growth_lookup.get(f"{_y}-{_m:02d}", 0))

    recent_sessions = (
        (
            await db.execute(
                select(Session).options(joinedload(Session.student), joinedload(Session.user)).order_by(Session.created_at.desc()).limit(10)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    recent_payments = (
        (await db.execute(select(Payment).options(joinedload(Payment.payee)).order_by(Payment.payment_date.desc()).limit(5))).scalars().all()
    )

    new_tutors = (
        (
            await db.execute(
                select(User).where(User.role == UserRole.tutor, User.created_at >= this_month_start).order_by(User.created_at.desc()).limit(5)
            )
        )
        .scalars()
        .all()
    )

    return {
        "now": now,
        "revenue_alltime": revenue_alltime,
        "revenue_this_month": revenue_this_month,
        "revenue_this_year": revenue_this_year,
        "total_payout_obligations": total_payout_obligations,
        "profit_margin": profit_margin,
        "mom_trend": mom_trend,
        "active_tutors": active_tutors,
        "active_students": active_students,
        "sessions_this_month": sessions_this_month,
        "sessions_pct_change": sessions_pct_change,
        "hours_this_month": round(hours_this_month_raw, 1),
        "hours_pct_change": hours_pct_change,
        "completion_rate": completion_rate,
        "cancellation_rate": cancellation_rate,
        "avg_students_per_tutor": avg_students_per_tutor,
        "top_by_hours": top_by_hours,
        "top_by_revenue": top_by_revenue,
        "inactive_tutors": inactive_tutors,
        "tutors_with_balance": tutors_with_balance,
        "at_risk_students": at_risk_students,
        "new_students": new_students,
        "students_no_active_tutor": students_no_active_tutor,
        "outstanding_balance": outstanding_balance,
        "tutors_no_payout": tutors_no_payout,
        "recent_sessions": recent_sessions,
        "recent_payments": recent_payments,
        "new_tutors": new_tutors,
        "students_chart_labels": students_chart_labels,
        "students_chart_data": students_chart_data,
    }
