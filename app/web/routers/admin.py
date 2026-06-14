import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.core.database import get_db
from app.utils import cap_name
from app.models.user import PayoutType, User, UserRole
from app.web.deps import require_admin

router = APIRouter(prefix="/admin", tags=["Web Admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.role == UserRole.tutor).order_by(User.created_at.desc()))
    tutors = result.scalars().all()
    return templates.TemplateResponse(request, "admin/users.html", {"user": user, "active_page": "admin_users", "tutors": tutors})


@router.get("/users/new", response_class=HTMLResponse)
async def admin_users_new(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/users_new.html", {"user": user, "active_page": "admin_users", "PayoutType": PayoutType})


@router.post("/users")
async def admin_users_create(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    payout_type: str = Form(default=""),
    payout_hourly_rate: float = Form(default=None),
    payout_percentage: float = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return RedirectResponse(url="/admin/users/new", status_code=303)

    new_user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        role=UserRole.tutor,
        is_active=True,
        payout_type=PayoutType(payout_type) if payout_type else None,
        payout_hourly_rate=payout_hourly_rate,
        payout_percentage=payout_percentage,
    )
    db.add(new_user)
    await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle-active")
async def admin_toggle_active(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    tutor = result.scalar_one_or_none()
    if tutor and not tutor.is_admin:
        tutor.is_active = not tutor.is_active
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/update-payout")
async def admin_update_payout(
    user_id: uuid.UUID,
    payout_type: str = Form(default=""),
    payout_hourly_rate: float = Form(default=None),
    payout_percentage: float = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    tutor = result.scalar_one_or_none()
    if tutor and not tutor.is_admin:
        tutor.payout_type = PayoutType(payout_type) if payout_type else None
        tutor.payout_hourly_rate = payout_hourly_rate
        tutor.payout_percentage = payout_percentage
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)
