import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models.payee import Payee
from app.models.user import User
from app.schemas.payee import PayeeCreate, PayeeResponse, PayeeUpdate

router = APIRouter(prefix="/payees", tags=["payees"])


@router.post("/", response_model=PayeeResponse, status_code=status.HTTP_201_CREATED)
async def create_payee(
    payee_in: PayeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payee = Payee(**payee_in.model_dump(), user_id=current_user.id)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


@router.get("/", response_model=list[PayeeResponse])
async def get_payees(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Payee).where(Payee.user_id == current_user.id).offset(offset).limit(limit))
    return result.scalars().all()


@router.get("/{payee_id}", response_model=PayeeResponse)
async def get_payee(
    payee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Payee).where(Payee.id == payee_id, Payee.user_id == current_user.id))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")
    return payee


@router.patch("/{payee_id}", response_model=PayeeResponse)
async def update_payee(
    payee_id: uuid.UUID,
    updates: PayeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Payee).where(Payee.id == payee_id, Payee.user_id == current_user.id))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(payee, field, value)

    await db.commit()
    await db.refresh(payee)
    return payee


@router.delete("/{payee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payee(
    payee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Payee).where(Payee.id == payee_id, Payee.user_id == current_user.id))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")

    await db.delete(payee)
    await db.commit()
