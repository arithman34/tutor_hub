import secrets
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.google_calendar_token import GoogleCalendarToken
from app.models.student import Student
from app.models.user import User
from app.services import google_calendar as google_calendar_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(prefix="/calendar", tags=["Calendar"])
templates = Jinja2Templates(directory="templates")

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@router.get("")
async def calendar_page(user: User = Depends(get_current_user_from_cookie)):
    return RedirectResponse(url="/sessions", status_code=303)


@router.get("/create", response_class=HTMLResponse)
async def calendar_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user.id))
    if not result.scalar_one_or_none():
        return RedirectResponse(url="/connections?error=not_connected")

    students_result = await db.execute(
        select(Student).where(Student.user_id == user.id, Student.is_active == True).order_by(Student.first_name, Student.last_name)
    )
    students = students_result.scalars().all()

    return templates.TemplateResponse(
        request,
        "calendar/create.html",
        {
            "user": user,
            "active_page": "sessions",
            "students": students,
            "days": _DAYS,
            "form_error": request.query_params.get("error"),
        },
    )


@router.post("/create")
async def calendar_create(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    form = await request.form()
    session_type = form.get("session_type", "oneoff")

    student_id_raw = str(form.get("student_id", "")).strip()
    if not student_id_raw:
        return RedirectResponse(url="/calendar/create?error=no_student", status_code=303)
    student_result = await db.execute(
        select(Student).where(
            Student.id == uuid.UUID(student_id_raw),
            Student.user_id == user.id,
        )
    )
    student = student_result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/calendar/create?error=no_student", status_code=303)
    title = google_calendar_service.build_event_title(student.first_name)
    location = user.address

    try:
        if session_type == "oneoff":
            await google_calendar_service.create_one_off_event(
                user_id=user.id,
                summary=title,
                date_str=str(form.get("date", "")),
                start_time=str(form.get("start_time", "")),
                end_time=str(form.get("end_time", "")),
                db=db,
                location=location,
            )
        else:
            day_configs = []
            for i in range(7):
                if form.get(f"day_{i}_enabled"):
                    day_configs.append(
                        {
                            "weekday": i,
                            "start": str(form.get(f"day_{i}_start", "09:00")),
                            "end": str(form.get(f"day_{i}_end", "10:00")),
                        }
                    )
            if not day_configs:
                return RedirectResponse(url="/calendar/create?error=no_days", status_code=303)

            await google_calendar_service.create_recurring_events(
                user_id=user.id,
                summary=title,
                day_configs=day_configs,
                start_date_str=str(form.get("start_date", "")),
                end_date_str=str(form.get("end_date", "")),
                interval_weeks=max(1, int(form.get("interval_weeks", "1") or 1)),
                db=db,
                location=location,
            )
    except Exception as exc:
        return RedirectResponse(url=f"/calendar/create?error={exc}", status_code=303)

    return RedirectResponse(url="/sessions?created=1", status_code=303)


@router.get("/connect")
async def calendar_connect(user: User = Depends(get_current_user_from_cookie)):
    state = secrets.token_urlsafe(32)
    url = google_calendar_service.build_connect_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie("gcal_state", state, max_age=300, httponly=True, samesite="lax")
    return response


@router.get("/callback")
async def calendar_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if error:
        return RedirectResponse(url="/connections?error=access_denied")

    stored_state = request.cookies.get("gcal_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/connections?error=invalid_state")

    try:
        await google_calendar_service.exchange_code(code, user.id, db)
    except Exception:
        return RedirectResponse(url="/connections?error=token_exchange_failed")

    response = RedirectResponse(url="/connections?connected=1", status_code=303)
    response.delete_cookie("gcal_state")
    return response


@router.post("/disconnect")
async def calendar_disconnect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user.id))
    token = result.scalar_one_or_none()
    if token:
        await db.delete(token)
        await db.commit()
    return RedirectResponse(url="/connections", status_code=303)
