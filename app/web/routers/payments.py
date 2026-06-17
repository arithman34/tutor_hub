import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.payee import Payee
from app.models.user import User
from app.services import payment as payment_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Payments"])
templates = Jinja2Templates(directory="templates")


@router.get("/payments", response_class=HTMLResponse)
async def payments_list(
    request: Request,
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    payments = await payment_service.list_payments(db, user, q=q)
    return templates.TemplateResponse(
        request,
        "payments/index.html",
        {
            "user": user,
            "active_page": "payments",
            "payments": payments,
            "q": q,
        },
    )


@router.get("/payments/new", response_class=HTMLResponse)
async def payments_new(
    request: Request,
    payee_id: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    payees = (await db.execute(select(Payee).order_by(Payee.first_name))).scalars().all()
    return templates.TemplateResponse(
        request,
        "payments/new.html",
        {
            "user": user,
            "active_page": "payments",
            "payees": payees,
            "selected_payee_id": payee_id,
        },
    )


@router.post("/payments")
async def payments_create(
    payee_id: str = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    payment_reference: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    payment_date_dt = datetime.strptime(payment_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    await payment_service.create_payment(
        db,
        user=user,
        payee_id=uuid.UUID(payee_id),
        amount=amount,
        payment_date=payment_date_dt,
        payment_reference=payment_reference or None,
    )
    return RedirectResponse(url="/payments", status_code=303)
