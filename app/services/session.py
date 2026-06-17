import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.session import Session
from app.models.student import Student
from app.models.user import User
from app.services import google_docs as gdocs_service


async def list_sessions(
    db: AsyncSession,
    user: User,
    q: str = "",
    limit: int = 20,
    offset: int = 0,
) -> list[Session]:
    if user.is_admin:
        stmt = select(Session).options(joinedload(Session.student), joinedload(Session.user))
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                Session.student_id.in_(select(Student.id).where(or_(Student.first_name.ilike(pattern), Student.last_name.ilike(pattern))))
            )
    else:
        stmt = select(Session).where(Session.user_id == user.id)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                Session.student_id.in_(select(Student.id).where(or_(Student.first_name.ilike(pattern), Student.last_name.ilike(pattern))))
            )
    stmt = stmt.order_by(Session.session_date.desc()).offset(offset).limit(limit)
    return list((await db.execute(stmt)).unique().scalars().all())


async def get_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> Session:
    result = await db.execute(select(Session).options(joinedload(Session.student)).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    if not user.is_admin and session.user_id != user.id:
        raise ForbiddenError("Not authorized to access this session")
    return session


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    student_id: uuid.UUID,
    session_date: datetime,
    session_start_time: datetime,
    session_end_time: datetime,
    is_no_show: bool = False,
    zoom_summary_raw: str | None = None,
    zoom_meeting_uuid: str | None = None,
    work_covered: str | None = None,
    student_actions: str | None = None,
    tutor_actions: str | None = None,
    next_lesson_focus: str | None = None,
    topic_tags: str | None = None,
    calendar_event_id: str | None = None,
    calendar_recurring_id: str | None = None,
    calendar_html_link: str | None = None,
) -> Session:
    if is_no_show:
        zoom_summary_raw = None
        work_covered = None
        student_actions = None
        tutor_actions = None
        next_lesson_focus = None
        topic_tags = None

    session = Session(
        user_id=user_id,
        student_id=student_id,
        session_date=session_date,
        session_start_time=session_start_time,
        session_end_time=session_end_time,
        is_no_show=is_no_show,
        zoom_summary_raw=zoom_summary_raw,
        zoom_meeting_uuid=zoom_meeting_uuid,
        work_covered=work_covered,
        student_actions=student_actions,
        tutor_actions=tutor_actions,
        next_lesson_focus=next_lesson_focus,
        topic_tags=topic_tags,
        calendar_event_id=calendar_event_id,
        calendar_recurring_id=calendar_recurring_id,
        calendar_html_link=calendar_html_link,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    try:
        student = (await db.execute(select(Student).where(Student.id == session.student_id))).scalar_one_or_none()
        if student and student.google_doc_id:
            all_sessions = (await db.execute(select(Session).where(Session.student_id == student.id).order_by(Session.session_date))).scalars().all()
            payee = None
            if student.payee_id:
                payee = (await db.execute(select(Payee).where(Payee.id == student.payee_id))).scalar_one_or_none()
            await gdocs_service.update_ilp_document(user_id, student.google_doc_id, student, payee, list(all_sessions), db)
            session.ilp_generated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        pass

    return session


async def update_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user: User,
    updates: dict,
) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    if not user.is_admin and session.user_id != user.id:
        raise ForbiddenError("Not authorized to update this session")

    if updates.get("is_no_show"):
        for field in ["work_covered", "student_actions", "tutor_actions", "next_lesson_focus", "topic_tags", "zoom_summary_raw"]:
            if field not in updates:
                updates[field] = None

    for key, value in updates.items():
        setattr(session, key, value)

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> None:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    if not user.is_admin and session.user_id != user.id:
        raise ForbiddenError("Not authorized to delete this session")
    await db.delete(session)
    await db.commit()
