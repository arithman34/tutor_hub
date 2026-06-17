import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.user import User
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.services import student as student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/", response_model=list[StudentResponse])
async def get_students(
    q: str = Query(default=""),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await student_service.list_students(db, current_user, q=q)


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_in: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = (
        student_in.tutor_id
        if current_user.is_admin and student_in.tutor_id is not None
        else current_user.id
    )
    try:
        return await student_service.create_student(
            db,
            calling_user=current_user,
            user_id=user_id,
            first_name=student_in.first_name,
            last_name=student_in.last_name,
            level=student_in.level,
            hourly_rate=student_in.hourly_rate,
            payee_id=student_in.payee_id,
            zoom_meeting_id=student_in.zoom_meeting_id,
            google_doc_id=student_in.google_doc_id,
            onedrive_shared_link=student_in.onedrive_shared_link,
        )
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create students")


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await student_service.get_student(db, student_id, current_user)
    except (NotFoundError, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    updates: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await student_service.update_student(db, student_id, current_user, updates.model_dump(exclude_unset=True))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{student_id}/toggle-active", response_model=StudentResponse)
async def toggle_active(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await student_service.toggle_active(db, student_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this student")


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await student_service.delete_student(db, student_id, current_user)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    except ForbiddenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete students")
