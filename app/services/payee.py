import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import User
from app.utils import cap_name

_session_hours = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 3600


async def list_payees(db: AsyncSession, user: User, q: str = "") -> list[Payee]:
    if not user.is_admin:
        raise ForbiddenError("Only admins can view payees")
    stmt = select(Payee).options(joinedload(Payee.students), joinedload(Payee.user)).order_by(Payee.first_name)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Payee.first_name.ilike(pattern), Payee.last_name.ilike(pattern)))
    return list((await db.execute(stmt)).unique().scalars().all())


async def get_payee(db: AsyncSession, payee_id: uuid.UUID, user: User) -> Payee:
    if not user.is_admin:
        raise ForbiddenError("Only admins can view payees")
    result = await db.execute(select(Payee).options(joinedload(Payee.students)).where(Payee.id == payee_id))
    payee = result.unique().scalar_one_or_none()
    if not payee:
        raise NotFoundError("Payee not found")
    return payee


async def create_payee(
    db: AsyncSession,
    user: User,
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone_number: str | None = None,
    bank_reference_pattern: str | None = None,
) -> Payee:
    if not user.is_admin:
        raise ForbiddenError("Only admins can create payees")
    payee = Payee(
        user_id=user.id,
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        email=email or None,
        phone_number=phone_number or None,
        bank_reference_pattern=bank_reference_pattern or None,
    )
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def update_payee(
    db: AsyncSession,
    payee_id: uuid.UUID,
    user: User,
    updates: dict,
) -> Payee:
    if not user.is_admin:
        raise ForbiddenError("Only admins can update payees")
    result = await db.execute(select(Payee).where(Payee.id == payee_id))
    payee = result.scalar_one_or_none()
    if not payee:
        raise NotFoundError("Payee not found")

    if "first_name" in updates and updates["first_name"]:
        updates["first_name"] = cap_name(updates["first_name"])
    if "last_name" in updates and updates["last_name"]:
        updates["last_name"] = cap_name(updates["last_name"])

    for key, value in updates.items():
        setattr(payee, key, value)

    payee.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(payee)
    return payee


async def delete_payee(db: AsyncSession, payee_id: uuid.UUID, user: User) -> None:
    if not user.is_admin:
        raise ForbiddenError("Only admins can delete payees")
    result = await db.execute(select(Payee).where(Payee.id == payee_id))
    payee = result.scalar_one_or_none()
    if not payee:
        raise NotFoundError("Payee not found")
    await db.delete(payee)
    await db.commit()


async def get_balances(db: AsyncSession, payee_ids: list[uuid.UUID]) -> dict[str, float]:
    """Returns {payee_id_str: balance} where balance = payments received - session costs."""
    if not payee_ids:
        return {}

    paid_rows = (
        await db.execute(
            select(Payment.payee_id, func.sum(Payment.amount).label("total")).where(Payment.payee_id.in_(payee_ids)).group_by(Payment.payee_id)
        )
    ).all()

    cost_rows = (
        await db.execute(
            select(Student.payee_id, func.sum(_session_hours * Student.hourly_rate).label("total"))
            .join(Session, Session.student_id == Student.id)
            .where(Student.payee_id.in_(payee_ids), Student.hourly_rate.isnot(None))
            .group_by(Student.payee_id)
        )
    ).all()

    paid = {str(r.payee_id): float(r.total or 0) for r in paid_rows}
    cost = {str(r.payee_id): float(r.total or 0) for r in cost_rows}
    return {str(pid): round(paid.get(str(pid), 0) - cost.get(str(pid), 0), 2) for pid in payee_ids}
