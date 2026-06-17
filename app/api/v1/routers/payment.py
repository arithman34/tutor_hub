import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentResponse, PaymentUpdate
from app.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/", response_model=list[PaymentResponse])
async def get_payments(
    q: str = Query(default=""),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payment_service.list_payments(db, current_user, q=q, limit=limit, offset=offset)
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view payments")


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_in: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payment_service.create_payment(
            db,
            user=current_user,
            payee_id=payment_in.payee_id,
            amount=payment_in.amount,
            payment_date=payment_in.payment_date,
            payment_reference=payment_in.payment_reference,
        )
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create payments")


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payment_service.get_payment(db, payment_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view payments")


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: uuid.UUID,
    updates: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await payment_service.update_payment(db, payment_id, current_user, updates.model_dump(exclude_unset=True))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update payments")


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await payment_service.delete_payment(db, payment_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete payments")
