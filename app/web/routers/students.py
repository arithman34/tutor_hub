import re
import uuid

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.session import Session
from app.models.user import User, UserRole
from app.services import student as student_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Students"])
templates = Jinja2Templates(directory="templates")


def _doc_id_from_url(url: str) -> str | None:
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


@router.get("/students", response_class=HTMLResponse)
async def students_list(
    request: Request,
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    students = await student_service.list_students(db, user, q=q)
    return templates.TemplateResponse(request, "students/index.html", {
        "user": user, "active_page": "students", "students": students, "q": q,
    })


@router.get("/students/new", response_class=HTMLResponse)
async def students_new(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/students", status_code=303)
    tutors_result = await db.execute(
        select(User).where(User.role.in_([UserRole.tutor, UserRole.admin_tutor]), User.is_active).order_by(User.first_name)
    )
    tutors = tutors_result.scalars().all()
    payees_result = await db.execute(select(Payee).order_by(Payee.first_name))
    payees = payees_result.scalars().all()
    return templates.TemplateResponse(request, "students/new.html", {
        "user": user, "active_page": "students", "tutors": tutors, "payees": payees,
    })


@router.post("/students")
async def students_create(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    tutor_id: str = Form(...),
    level: str = Form(default=""),
    hourly_rate: float = Form(default=0.0),
    payee_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        return RedirectResponse(url="/students", status_code=303)
    await student_service.create_student(
        db,
        calling_user=user,
        user_id=uuid.UUID(tutor_id),
        first_name=first_name,
        last_name=last_name,
        level=level or None,
        hourly_rate=hourly_rate or None,
        payee_id=uuid.UUID(payee_id) if payee_id else None,
    )
    return RedirectResponse(url="/students", status_code=303)


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_detail(
    student_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    try:
        student = await student_service.get_student(db, student_id, user)
    except (NotFoundError, ForbiddenError):
        return RedirectResponse(url="/students", status_code=303)

    sessions_result = await db.execute(
        select(Session).where(Session.student_id == student_id).order_by(Session.session_date.desc()).limit(10)
    )
    sessions = sessions_result.scalars().all()

    payees = []
    if user.is_admin:
        payees_result = await db.execute(select(Payee).order_by(Payee.first_name))
        payees = payees_result.scalars().all()

    return templates.TemplateResponse(request, "students/detail.html", {
        "user": user, "active_page": "students", "student": student, "sessions": sessions, "payees": payees,
    })


@router.post("/students/{student_id}/update")
async def student_update(
    student_id: uuid.UUID,
    first_name: str = Form(...),
    last_name: str = Form(default=""),
    level: str = Form(default=""),
    hourly_rate: float = Form(default=0.0),
    payee_id: str = Form(default=""),
    ilp_url: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    updates = {
        "first_name": first_name,
        "level": level or None,
        "hourly_rate": hourly_rate or None,
        "google_doc_id": _doc_id_from_url(ilp_url) if ilp_url else None,
    }
    if last_name:
        updates["last_name"] = last_name
    if user.is_admin:
        updates["payee_id"] = uuid.UUID(payee_id) if payee_id else None

    try:
        await student_service.update_student(db, student_id, user, updates)
    except (NotFoundError, ForbiddenError):
        return RedirectResponse(url="/students", status_code=303)
    return RedirectResponse(url=f"/students/{student_id}", status_code=303)


@router.post("/students/{student_id}/toggle-active")
async def student_toggle_active(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    try:
        await student_service.toggle_active(db, student_id, user)
    except (NotFoundError, ForbiddenError):
        pass
    return RedirectResponse(url=f"/students/{student_id}", status_code=303)


@router.post("/students/{student_id}/delete")
async def student_delete(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    try:
        await student_service.delete_student(db, student_id, user)
    except (NotFoundError, ForbiddenError):
        pass
    return RedirectResponse(url="/students", status_code=303)
