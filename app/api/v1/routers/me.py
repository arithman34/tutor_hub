from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import user as user_service

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
    return await user_service.update_profile(
        db,
        current_user=current_user,
        email=updates.email,
        password=updates.password,
        first_name=updates.first_name,
        last_name=updates.last_name,
    )
