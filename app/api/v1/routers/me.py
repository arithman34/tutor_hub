from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, hash_password
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/", response_model=UserResponse)
async def update_my_profile(
    updates: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if updates.email is not None:
        user.email = updates.email
    if updates.password is not None:
        user.hashed_password = hash_password(updates.password)
    if updates.first_name is not None:
        user.first_name = updates.first_name
    if updates.last_name is not None:
        user.last_name = updates.last_name

    await db.commit()
    await db.refresh(user)
    return user
