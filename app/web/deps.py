from fastapi import Cookie, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, decode_access_token, verify_and_rotate_refresh_token
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

_REFRESH_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 86400


class NotAuthenticatedException(Exception):
    pass


class NotAdminException(Exception):
    pass


async def get_current_user_from_cookie(
    response: Response,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Fast path: valid access token
    if access_token:
        email = decode_access_token(access_token)
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user

    # Slow path: try refresh token
    if refresh_token:
        rotated = await verify_and_rotate_refresh_token(db, refresh_token)
        if rotated:
            user, new_refresh_token = rotated
            new_access_token = create_access_token({"sub": user.email})
            response.set_cookie(key="access_token", value=new_access_token, httponly=True, samesite="lax")
            response.set_cookie(key="refresh_token", value=new_refresh_token, httponly=True, samesite="lax", max_age=_REFRESH_COOKIE_MAX_AGE)
            return user

    raise NotAuthenticatedException()


async def require_admin(user: User = Depends(get_current_user_from_cookie)) -> User:
    if not user.is_admin:
        raise NotAdminException()
    return user
