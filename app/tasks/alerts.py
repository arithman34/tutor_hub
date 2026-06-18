import asyncio
import uuid

import resend
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import User, UserRole
from app.worker import celery_app

_s_hours = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 3600


async def _fetch_overdue_data() -> tuple[str | None, list[dict]]:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine) as db:
            admin = (
                await db.execute(
                    select(User).where(User.role.in_([UserRole.admin, UserRole.admin_tutor])).limit(1)
                )
            ).scalar_one_or_none()
            if not admin:
                return None, []

            cost_rows = (
                await db.execute(
                    select(Student.payee_id, func.sum(_s_hours * Student.hourly_rate).label("cost"))
                    .join(Session, Session.student_id == Student.id)
                    .where(Student.payee_id.isnot(None), Student.hourly_rate.isnot(None))
                    .group_by(Student.payee_id)
                )
            ).all()
            paid_rows = (
                await db.execute(
                    select(Payment.payee_id, func.sum(Payment.amount).label("paid")).group_by(Payment.payee_id)
                )
            ).all()

            cost_map = {str(r.payee_id): float(r.cost or 0) for r in cost_rows}
            paid_map = {str(r.payee_id): float(r.paid or 0) for r in paid_rows}

            overdue_ids = [uuid.UUID(pid) for pid in cost_map if cost_map[pid] > paid_map.get(pid, 0)]
            if not overdue_ids:
                return admin.email, []

            payees = (await db.execute(select(Payee).where(Payee.id.in_(overdue_ids)))).scalars().all()
            overdue = [
                {
                    "name": f"{p.first_name} {p.last_name}",
                    "balance": round(cost_map[str(p.id)] - paid_map.get(str(p.id), 0), 2),
                }
                for p in payees
            ]
            return admin.email, overdue
    finally:
        await engine.dispose()


@celery_app.task(name="app.tasks.alerts.send_overdue_alerts")
def send_overdue_alerts() -> None:
    admin_email, overdue_payees = asyncio.run(_fetch_overdue_data())
    if not admin_email or not overdue_payees:
        return

    lines = [f"  - {p['name']}: £{p['balance']:.2f} outstanding" for p in overdue_payees]
    body = (
        f"The following {len(overdue_payees)} payee(s) have a negative credit balance:\n\n"
        + "\n".join(lines)
        + "\n\nPlease log in to TutorHub to review and record payments.\n"
    )

    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.from_email,
        "to": [admin_email],
        "subject": f"TutorHub: {len(overdue_payees)} overdue payment(s)",
        "text": body,
    })
