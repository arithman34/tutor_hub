import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User

security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def get_user(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user(db, email)
    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    db_token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.commit()
    return token


async def verify_and_rotate_refresh_token(db: AsyncSession, token: str) -> tuple[User, str] | None:
    """Validates the token, revokes it, issues a new one, and returns (user, new_token)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == _hash_token(token))
        .where(RefreshToken.revoked == False)  # noqa: E712
        .where(RefreshToken.expires_at > now)
    )
    db_token = result.scalar_one_or_none()
    if db_token is None:
        return None

    db_token.revoked = True

    new_raw = secrets.token_urlsafe(64)
    new_db_token = RefreshToken(
        user_id=db_token.user_id,
        token_hash=_hash_token(new_raw),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_db_token)

    user_result = await db.execute(select(User).where(User.id == db_token.user_id))
    user = user_result.scalar_one_or_none()

    await db.commit()

    if user is None or not user.is_active:
        return None

    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == _hash_token(token)))
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.revoked = True
        await db.commit()


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = decode_access_token(token)
    if email is None:
        raise credentials_exception

    user = await get_user(db, email)
    if user is None:
        raise credentials_exception

    return user
