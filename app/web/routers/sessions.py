import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.models.google_calendar_token import GoogleCalendarToken
from app.models.session import Session
from app.models.student import Student
from app.models.user import User
from app.services import google_calendar as gcal_svc
from app.services.ai import parse_zoom_summary
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Sessions"])
templates = Jinja2Templates(directory="templates")


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(
    request: Request,
    q: str = Query(default=""),
    status: str = Query(default="all"),
    period: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    # Admins see all logged sessions across all tutors
    if user.is_admin:
        stmt = (
            select(Session)
            .options(joinedload(Session.student), joinedload(Session.user))
            .where(Session.calendar_event_id.isnot(None))
            .order_by(Session.session_date.desc())
        )
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(Session.student_id.in_(
                select(Student.id).where(or_(Student.first_name.ilike(pattern), Student.last_name.ilike(pattern)))
            ))
        sessions = (await db.execute(stmt)).unique().scalars().all()
        return templates.TemplateResponse(request, "sessions/index.html", {"user": user, "active_page": "sessions", "sessions": sessions, "q": q})

    # Tutors require Google Calendar.
    token = (await db.execute(
        select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user.id)
    )).scalar_one_or_none()

    if not token:
        return RedirectResponse(url="/connections?error=not_connected", status_code=303)

    label = token.label or "Tuition"
    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=365)
    time_max = now + timedelta(days=365)

    error = None
    events = []
    try:
        events = await gcal_svc.fetch_events(user.id, label, time_min, time_max, db)
    except Exception as exc:
        error = str(exc)

    # Sessions logged via the app, keyed by the Google Calendar event id they came from.
    logged = (await db.execute(
        select(Session).options(joinedload(Session.student)).where(Session.user_id == user.id)
    )).unique().scalars().all()
    logged_by_event = {s.calendar_event_id: s for s in logged if s.calendar_event_id}

    students = (await db.execute(
        select(Student).where(Student.user_id == user.id, Student.is_active == True)
    )).scalars().all()
    student_by_name = {f"{s.first_name} {s.last_name}": s for s in students}

    items = []
    for event in events:
        parsed = gcal_svc.parse_event(event)
        sess = logged_by_event.get(parsed["event_id"])
        student = student_by_name.get(parsed["student_name"])
        items.append({
            **parsed,
            "logged": sess is not None,
            "session_id": str(sess.id) if sess else None,
            "student_id": str(student.id) if student else None,
        })

    # Past + today newest-first, then upcoming sessions ascending.
    today_str = now.strftime("%Y-%m-%d")
    past = sorted(
        (i for i in items if i["date"] <= today_str),
        key=lambda i: f"{i['date']}T{i['start_time'] or '00:00'}",
        reverse=True,
    )
    future = sorted(
        (i for i in items if i["date"] > today_str),
        key=lambda i: f"{i['date']}T{i['start_time'] or '00:00'}",
    )
    items = past + future

    if status == "logged":
        items = [i for i in items if i["logged"]]
    elif status == "unlogged":
        items = [i for i in items if not i["logged"]]

    if period == "past":
        items = [i for i in items if i["date"] < today_str]
    elif period == "today":
        items = [i for i in items if i["date"] == today_str]
    elif period == "future":
        items = [i for i in items if i["date"] > today_str]

    return templates.TemplateResponse(request, "sessions/google.html", {
        "user": user, "active_page": "sessions",
        "items": items, "status": status, "period": period, "label": label, "error": error,
    })


@router.get("/sessions/new", response_class=HTMLResponse)
async def sessions_new(
    request: Request,
    student_id: str = Query(default=""),
    date: str = Query(default=""),
    start_time: str = Query(default=""),
    end_time: str = Query(default=""),
    event_id: str = Query(default=""),
    html_link: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if user.is_admin:
        return RedirectResponse(url="/sessions", status_code=303)
    result = await db.execute(select(Student).where(Student.user_id == user.id, Student.is_active == True).order_by(Student.first_name))
    students = result.scalars().all()
    return templates.TemplateResponse(request, "sessions/new.html", {
        "user": user,
        "active_page": "sessions",
        "students": students,
        "prefill_student_id": student_id,
        "prefill_date": date,
        "prefill_start": start_time,
        "prefill_end": end_time,
        "prefill_event_id": event_id,
        "prefill_html_link": html_link,
    })


@router.post("/sessions/zoom-parse", response_class=JSONResponse)
async def sessions_zoom_parse(
    zoom_summary: str = Form(...),
    user: User = Depends(get_current_user_from_cookie),
):
    if user.is_admin:
        return JSONResponse({"error": "Admins cannot log sessions"}, status_code=403)
    parsed = await parse_zoom_summary(zoom_summary)
    return JSONResponse({
        "work_covered": parsed.work_covered,
        "student_actions": parsed.student_actions,
        "tutor_actions": parsed.tutor_actions,
        "next_lesson_focus": parsed.next_lesson_focus,
        "topic_tags": parsed.topic_tags,
    })


@router.post("/sessions")
async def sessions_create(
    student_id: str = Form(...),
    session_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    is_no_show: str = Form(default=""),
    zoom_summary_raw: str = Form(default=""),
    work_covered: str = Form(default=""),
    student_actions: str = Form(default=""),
    tutor_actions: str = Form(default=""),
    next_lesson_focus: str = Form(default=""),
    topic_tags: str = Form(default=""),
    calendar_event_id: str = Form(default=""),
    calendar_html_link: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if user.is_admin:
        return RedirectResponse(url="/sessions", status_code=303)
    start_dt = datetime.strptime(f"{session_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(f"{session_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    no_show = bool(is_no_show)
    session = Session(
        user_id=user.id,
        student_id=uuid.UUID(student_id),
        session_date=start_dt,
        session_start_time=start_dt,
        session_end_time=end_dt,
        is_no_show=no_show,
        zoom_summary_raw=None if no_show else (zoom_summary_raw or None),
        work_covered=None if no_show else (work_covered or None),
        student_actions=None if no_show else (student_actions or None),
        tutor_actions=None if no_show else (tutor_actions or None),
        next_lesson_focus=None if no_show else (next_lesson_focus or None),
        topic_tags=None if no_show else (topic_tags or None),
        calendar_event_id=calendar_event_id or None,
        calendar_html_link=calendar_html_link or None,
    )
    db.add(session)
    await db.commit()
    return RedirectResponse(url="/sessions", status_code=303)


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(session_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user_from_cookie)):
    result = await db.execute(select(Session).options(joinedload(Session.student)).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session or (not user.is_admin and session.user_id != user.id):
        return RedirectResponse(url="/sessions", status_code=303)
    students = []
    if not user.is_admin:
        students = (await db.execute(
            select(Student).where(Student.user_id == user.id, Student.is_active == True).order_by(Student.first_name)
        )).scalars().all()
    return templates.TemplateResponse(request, "sessions/detail.html", {"user": user, "active_page": "sessions", "session": session, "students": students})


@router.post("/sessions/{session_id}/update")
async def session_update(
    session_id: uuid.UUID,
    student_id: str = Form(default=""),
    session_date: str = Form(default=""),
    start_time: str = Form(default=""),
    end_time: str = Form(default=""),
    is_no_show: str = Form(default=""),
    work_covered: str = Form(default=""),
    student_actions: str = Form(default=""),
    tutor_actions: str = Form(default=""),
    next_lesson_focus: str = Form(default=""),
    topic_tags: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session or (not user.is_admin and session.user_id != user.id):
        return RedirectResponse(url="/sessions", status_code=303)
    if student_id:
        session.student_id = uuid.UUID(student_id)
    if session_date and start_time and end_time:
        start_dt = datetime.strptime(f"{session_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{session_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        session.session_date = start_dt
        session.session_start_time = start_dt
        session.session_end_time = end_dt
    session.is_no_show = bool(is_no_show)
    session.work_covered = work_covered or None
    session.student_actions = student_actions or None
    session.tutor_actions = tutor_actions or None
    session.next_lesson_focus = next_lesson_focus or None
    session.topic_tags = topic_tags or None
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/delete")
async def session_delete(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session or (not user.is_admin and session.user_id != user.id):
        return RedirectResponse(url="/sessions", status_code=303)
    await db.delete(session)
    await db.commit()
    return RedirectResponse(url="/sessions", status_code=303)


