import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.utils import cap_name
from app.models.payee import Payee
from app.models.session import Session
from app.models.student import Student
from app.models.user import User, UserRole
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Students"])
templates = Jinja2Templates(directory="templates")


@router.get("/students", response_class=HTMLResponse)
async def students_list(request: Request, q: str = Query(default=""), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    stmt = select(Student).order_by(Student.created_at.desc())
    if user.is_admin:
        stmt = stmt.options(joinedload(Student.user))
    else:
        stmt = stmt.where(Student.user_id == user.id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Student.first_name.ilike(pattern), Student.last_name.ilike(pattern)))
    students = (await db.execute(stmt)).scalars().all()
    return templates.TemplateResponse(request, "students/index.html", {"user": user, "active_page": "students", "students": students, "q": q})


@router.get("/students/new", response_class=HTMLResponse)
async def students_new(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/students", status_code=303)
    tutors_result = await db.execute(select(User).where(User.role == UserRole.tutor, User.is_active).order_by(User.first_name))
    tutors = tutors_result.scalars().all()
    payees_result = await db.execute(select(Payee).order_by(Payee.first_name))
    payees = payees_result.scalars().all()
    return templates.TemplateResponse(request, "students/new.html", {"user": user, "active_page": "students", "tutors": tutors, "payees": payees})


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
    student = Student(
        user_id=uuid.UUID(tutor_id),
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        level=level or None,
        hourly_rate=hourly_rate or None,
        payee_id=uuid.UUID(payee_id) if payee_id else None,
    )
    db.add(student)
    await db.commit()
    return RedirectResponse(url="/students", status_code=303)


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_detail(student_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student or (not user.is_admin and student.user_id != user.id):
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
        "user": user,
        "active_page": "students",
        "student": student,
        "sessions": sessions,
        "payees": payees,
    })


@router.post("/students/{student_id}/update")
async def student_update(
    student_id: uuid.UUID,
    first_name: str = Form(...),
    last_name: str = Form(...),
    level: str = Form(default=""),
    hourly_rate: float = Form(default=0.0),
    payee_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student or (not user.is_admin and student.user_id != user.id):
        return RedirectResponse(url="/students", status_code=303)
    student.first_name = cap_name(first_name)
    student.last_name = cap_name(last_name)
    student.level = level or None
    student.hourly_rate = hourly_rate or None
    if user.is_admin:
        student.payee_id = uuid.UUID(payee_id) if payee_id else None
    student.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/students/{student_id}", status_code=303)


@router.post("/students/{student_id}/toggle-active")
async def student_toggle_active(student_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if student and (user.is_admin or student.user_id == user.id):
        student.is_active = not student.is_active
        await db.commit()
    return RedirectResponse(url=f"/students/{student_id}", status_code=303)


@router.post("/students/{student_id}/delete")
async def student_delete(student_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    if not user.is_admin:
        return RedirectResponse(url="/students", status_code=303)
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if student:
        await db.delete(student)
        await db.commit()
    return RedirectResponse(url="/students", status_code=303)
