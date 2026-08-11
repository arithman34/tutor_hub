from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import PayoutType, User, UserRole
from app.utils import pct_change as _pct_change

_mins = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 60


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
