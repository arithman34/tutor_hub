import uuid

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.payment import Payment
from app.models.user import User
from app.services import payee as payee_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Payees"])
templates = Jinja2Templates(directory="templates")


@router.get("/payees", response_class=HTMLResponse)
async def payees_list(
    request: Request,
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    payees = await payee_service.list_payees(db, user, q=q)
    balances = await payee_service.get_balances(db, [p.id for p in payees])
    return templates.TemplateResponse(
        request,
        "payees/index.html",
        {
            "user": user,
            "active_page": "payees",
            "payees": payees,
            "q": q,
            "balances": balances,
        },
    )


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
    await payee_service.create_payee(
        db,
        user=user,
        first_name=first_name,
        last_name=last_name,
        email=email or None,
        phone_number=phone_number or None,
        bank_reference_pattern=bank_reference_pattern or None,
    )
    return RedirectResponse(url="/payees", status_code=303)


@router.get("/payees/{payee_id}", response_class=HTMLResponse)
async def payee_detail(
    payee_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    try:
        payee = await payee_service.get_payee(db, payee_id, user)
    except (NotFoundError, ForbiddenError):
        return RedirectResponse(url="/payees", status_code=303)

    balances = await payee_service.get_balances(db, [payee_id])
    balance = balances.get(str(payee_id), 0.0)
    payments = (await db.execute(select(Payment).where(Payment.payee_id == payee_id).order_by(Payment.payment_date.desc()))).scalars().all()

    return templates.TemplateResponse(
        request,
        "payees/detail.html",
        {
            "user": user,
            "active_page": "payees",
            "payee": payee,
            "balance": balance,
            "payments": payments,
        },
    )


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
    updates = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email or None,
        "phone_number": phone_number or None,
        "bank_reference_pattern": bank_reference_pattern or None,
    }
    try:
        await payee_service.update_payee(db, payee_id, user, updates)
    except (NotFoundError, ForbiddenError):
        return RedirectResponse(url="/payees", status_code=303)
    return RedirectResponse(url=f"/payees/{payee_id}", status_code=303)
