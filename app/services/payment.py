import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.user import User


async def list_payments(
    db: AsyncSession,
    user: User,
    q: str = "",
    limit: int = 20,
    offset: int = 0,
) -> list[Payment]:
    if not user.is_admin:
        raise ForbiddenError("Only admins can view payments")
    stmt = select(Payment).options(joinedload(Payment.payee), joinedload(Payment.user)).order_by(Payment.payment_date.desc())
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Payment.payee_id.in_(select(Payee.id).where(or_(Payee.first_name.ilike(pattern), Payee.last_name.ilike(pattern)))))
    stmt = stmt.offset(offset).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_payment(db: AsyncSession, payment_id: uuid.UUID, user: User) -> Payment:
    if not user.is_admin:
        raise ForbiddenError("Only admins can view payments")
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise NotFoundError("Payment not found")
    return payment


async def create_payment(
    db: AsyncSession,
    user: User,
    payee_id: uuid.UUID,
    amount: float,
    payment_date: datetime,
    payment_reference: str | None = None,
) -> Payment:
    if not user.is_admin:
        raise ForbiddenError("Only admins can create payments")
    payment = Payment(
        user_id=user.id,
        payee_id=payee_id,
        amount=amount,
        payment_date=payment_date,
        payment_reference=payment_reference or None,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def update_payment(
    db: AsyncSession,
    payment_id: uuid.UUID,
    user: User,
    updates: dict,
) -> Payment:
    if not user.is_admin:
        raise ForbiddenError("Only admins can update payments")
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise NotFoundError("Payment not found")
    for key, value in updates.items():
        setattr(payment, key, value)
    await db.commit()
    await db.refresh(payment)
    return payment


async def delete_payment(db: AsyncSession, payment_id: uuid.UUID, user: User) -> None:
    if not user.is_admin:
        raise ForbiddenError("Only admins can delete payments")
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise NotFoundError("Payment not found")
    await db.delete(payment)
    await db.commit()
