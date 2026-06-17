import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.user import User
from app.schemas.payee import PayeeCreate, PayeeResponse, PayeeUpdate
from app.services import payee as payee_service

router = APIRouter(prefix="/payees", tags=["payees"])


@router.get("/", response_model=list[PayeeResponse])
async def get_payees(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payee_service.list_payees(db, current_user, q=q)
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view payees")


@router.post("/", response_model=PayeeResponse, status_code=status.HTTP_201_CREATED)
async def create_payee(
    payee_in: PayeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payee_service.create_payee(
            db,
            user=current_user,
            first_name=payee_in.first_name,
            last_name=payee_in.last_name,
            email=str(payee_in.email) if payee_in.email else None,
            phone_number=payee_in.phone_number,
            bank_reference_pattern=payee_in.bank_reference_pattern,
        )
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create payees")


@router.get("/{payee_id}/balance")
async def get_payee_balance(
    payee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await payee_service.get_payee(db, payee_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view payees")
    balances = await payee_service.get_balances(db, [payee_id])
    return {"balance": balances.get(str(payee_id), 0.0)}


@router.get("/{payee_id}", response_model=PayeeResponse)
async def get_payee(
    payee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payee_service.get_payee(db, payee_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view payees")


@router.patch("/{payee_id}", response_model=PayeeResponse)
async def update_payee(
    payee_id: uuid.UUID,
    updates: PayeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = updates.model_dump(exclude_unset=True)
    if "email" in raw and raw["email"] is not None:
        raw["email"] = str(raw["email"])
    try:
        return await payee_service.update_payee(db, payee_id, current_user, raw)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update payees")


@router.delete("/{payee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payee(
    payee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await payee_service.delete_payee(db, payee_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payee not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete payees")
