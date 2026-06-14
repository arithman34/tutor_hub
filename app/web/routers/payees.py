import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.models.payment import Payment
from app.models.payee import Payee
from app.models.session import Session
from app.models.student import Student
from app.models.user import User
from app.utils import cap_name
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Payees"])
templates = Jinja2Templates(directory="templates")

_session_hours = func.extract('epoch', Session.session_end_time - Session.session_start_time) / 3600


async def _balances(db: AsyncSession, payee_ids: list[uuid.UUID]) -> dict[str, float]:
    """Returns {payee_id_str: balance} for the given payees.
    Balance = total completed payments in - total session costs out.
    Positive = payee has credit. Negative = payee owes money.
    """
    if not payee_ids:
        return {}

    paid_rows = (await db.execute(
        select(Payment.payee_id, func.sum(Payment.amount).label("total"))
        .where(Payment.payee_id.in_(payee_ids))
        .group_by(Payment.payee_id)
    )).all()

    cost_rows = (await db.execute(
        select(Student.payee_id, func.sum(_session_hours * Student.hourly_rate).label("total"))
        .join(Session, Session.student_id == Student.id)
        .where(Student.payee_id.in_(payee_ids), Student.hourly_rate.isnot(None))
        .group_by(Student.payee_id)
    )).all()

    paid = {str(r.payee_id): float(r.total or 0) for r in paid_rows}
    cost = {str(r.payee_id): float(r.total or 0) for r in cost_rows}
    all_ids = {str(pid) for pid in payee_ids}
    return {
        pid: round(paid.get(pid, 0) - cost.get(pid, 0), 2)
        for pid in all_ids
    }


@router.get("/payees", response_class=HTMLResponse)
async def payees_list(request: Request, q: str = Query(default=""), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    stmt = select(Payee).options(joinedload(Payee.students), joinedload(Payee.user)).order_by(Payee.first_name)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Payee.first_name.ilike(pattern), Payee.last_name.ilike(pattern)))
    payees = (await db.execute(stmt)).unique().scalars().all()
    balances = await _balances(db, [p.id for p in payees])
    return templates.TemplateResponse(request, "payees/index.html", {
        "user": user, "active_page": "payees", "payees": payees, "q": q, "balances": balances,
    })


@router.get("/payees/new", response_class=HTMLResponse)
async def payees_new(request: Request, user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "payees/new.html", {"user": user, "active_page": "payees"})


@router.post("/payees")
async def payees_create(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(default=""),
    phone_number: str = Form(default=""),
    bank_reference_pattern: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    payee = Payee(
        user_id=user.id,
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        email=email or None,
        phone_number=phone_number or None,
        bank_reference_pattern=bank_reference_pattern or None,
    )
    db.add(payee)
    await db.commit()
    return RedirectResponse(url="/payees", status_code=303)


@router.get("/payees/{payee_id}", response_class=HTMLResponse)
async def payee_detail(payee_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    result = await db.execute(select(Payee).options(joinedload(Payee.students)).where(Payee.id == payee_id))
    payee = result.scalar_one_or_none()
    if not payee:
        return RedirectResponse(url="/payees", status_code=303)
    balances = await _balances(db, [payee_id])
    balance = balances.get(str(payee_id), 0.0)

    payments = (await db.execute(
        select(Payment)
        .where(Payment.payee_id == payee_id)
        .order_by(Payment.payment_date.desc())
    )).scalars().all()

    return templates.TemplateResponse(request, "payees/detail.html", {
        "user": user, "active_page": "payees", "payee": payee,
        "balance": balance, "payments": payments,
    })


@router.post("/payees/{payee_id}/update")
async def payee_update(
    payee_id: uuid.UUID,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(default=""),
    phone_number: str = Form(default=""),
    bank_reference_pattern: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    result = await db.execute(select(Payee).where(Payee.id == payee_id))
    payee = result.scalar_one_or_none()
    if not payee:
        return RedirectResponse(url="/payees", status_code=303)
    payee.first_name = cap_name(first_name)
    payee.last_name = cap_name(last_name)
    payee.email = email or None
    payee.phone_number = phone_number or None
    payee.bank_reference_pattern = bank_reference_pattern or None
    payee.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/payees/{payee_id}", status_code=303)
