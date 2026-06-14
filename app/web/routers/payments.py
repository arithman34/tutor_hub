import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.models.payment import Payment
from app.models.payee import Payee
from app.models.user import User
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Payments"])
templates = Jinja2Templates(directory="templates")


@router.get("/payments", response_class=HTMLResponse)
async def payments_list(request: Request, q: str = Query(default=""), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    stmt = select(Payment).options(joinedload(Payment.payee), joinedload(Payment.user)).order_by(Payment.payment_date.desc())
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Payment.payee_id.in_(
            select(Payee.id).where(or_(Payee.first_name.ilike(pattern), Payee.last_name.ilike(pattern)))
        ))
    payments = (await db.execute(stmt)).scalars().all()
    return templates.TemplateResponse(request, "payments/index.html", {"user": user, "active_page": "payments", "payments": payments, "q": q})


@router.get("/payments/new", response_class=HTMLResponse)
async def payments_new(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    result = await db.execute(select(Payee).order_by(Payee.first_name))
    payees = result.scalars().all()
    return templates.TemplateResponse(request, "payments/new.html", {"user": user, "active_page": "payments", "payees": payees})


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
    payment = Payment(
        user_id=user.id,
        payee_id=uuid.UUID(payee_id),
        amount=amount,
        payment_date=payment_date_dt,
        payment_reference=payment_reference or None,
    )
    db.add(payment)
    await db.commit()
    return RedirectResponse(url="/payments", status_code=303)
