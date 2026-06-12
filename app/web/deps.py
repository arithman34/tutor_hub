from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.core.database import get_db
from app.models.user import User


class NotAuthenticatedException(Exception):
    pass


async def get_current_user_from_cookie(access_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)) -> User:
    if not access_token:
        raise NotAuthenticatedException()

    email = decode_access_token(access_token)
    if not email:
        raise NotAuthenticatedException()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise NotAuthenticatedException()

    return user
