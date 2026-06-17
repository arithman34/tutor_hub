import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.user import User
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.services import session as session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=list[SessionResponse])
async def get_sessions(
    q: str = Query(default=""),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await session_service.list_sessions(db, current_user, q=q, limit=limit, offset=offset)


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_in: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await session_service.create_session(
        db,
        user_id=current_user.id,
        student_id=session_in.student_id,
        session_date=session_in.session_date,
        session_start_time=session_in.session_start_time,
        session_end_time=session_in.session_end_time,
        is_no_show=session_in.is_no_show,
        zoom_summary_raw=session_in.zoom_summary_raw,
        zoom_meeting_uuid=session_in.zoom_meeting_uuid,
        work_covered=session_in.work_covered,
        student_actions=session_in.student_actions,
        tutor_actions=session_in.tutor_actions,
        next_lesson_focus=session_in.next_lesson_focus,
        topic_tags=session_in.topic_tags,
        calendar_event_id=session_in.calendar_event_id,
        calendar_recurring_id=session_in.calendar_recurring_id,
        calendar_html_link=session_in.calendar_html_link,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await session_service.get_session(db, session_id, current_user)
    except (NotFoundError, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    updates: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await session_service.update_session(db, session_id, current_user, updates.model_dump(exclude_unset=True))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this session")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await session_service.delete_session(db, session_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this session")
