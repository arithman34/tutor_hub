from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.payment import Payment, PaymentStatus
from app.models.session import Session
from app.models.student import Student
from app.models.user import User
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Dashboard"])
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    total_students = await db.scalar(select(func.count()).select_from(Student).where(Student.user_id == user.id, Student.is_active))
    total_sessions = await db.scalar(select(func.count()).select_from(Session).where(Session.user_id == user.id))
    pending_payments = await db.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.pending,
        )
    )

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "user": user,
            "active_page": "dashboard",
            "total_students": total_students,
            "total_sessions": total_sessions,
            "pending_payments": pending_payments,
        },
    )
