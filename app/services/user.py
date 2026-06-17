import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import PayoutType, User, UserRole
from app.utils import cap_name


async def list_users(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[User]:
    result = await db.execute(select(User).offset(offset).limit(limit))
    return list(result.scalars().all())


async def list_tutors(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).where(User.role == UserRole.tutor).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


async def create_user(
    db: AsyncSession,
    current_user: User,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: str,
    is_active: bool = True,
) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Only admins can create users")

    if role == UserRole.admin.value or role == UserRole.admin:
        count = await db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.admin))
        if count and count > 0:
            raise ConflictError("An admin user already exists")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole(role) if isinstance(role, str) else role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_tutor(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    payout_type: str | None = None,
    payout_hourly_rate: float | None = None,
    payout_percentage: float | None = None,
) -> User | None:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return None

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        role=UserRole.tutor,
        is_active=True,
        payout_type=PayoutType(payout_type) if payout_type else None,
        payout_hourly_rate=payout_hourly_rate,
        payout_percentage=payout_percentage,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def toggle_active(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    if user.is_admin:
        raise ForbiddenError("Cannot toggle active status of an admin")
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user


async def activate(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


async def update_payout(
    db: AsyncSession,
    user_id: uuid.UUID,
    payout_type: str | None,
    payout_hourly_rate: float | None,
    payout_percentage: float | None,
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    if user.is_admin:
        raise ForbiddenError("Cannot update payout config for an admin")
    user.payout_type = PayoutType(payout_type) if payout_type else None
    user.payout_hourly_rate = payout_hourly_rate
    user.payout_percentage = payout_percentage
    await db.commit()
    await db.refresh(user)
    return user


async def update_profile(
    db: AsyncSession,
    current_user: User,
    email: str | None = None,
    password: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    if email is not None:
        current_user.email = email
    if password is not None:
        current_user.hashed_password = hash_password(password)
    if first_name is not None:
        current_user.first_name = first_name
    if last_name is not None:
        current_user.last_name = last_name
    await db.commit()
    await db.refresh(current_user)
    return current_user
