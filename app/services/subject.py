import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.subject import Subject


async def list_subjects(db: AsyncSession) -> list[Subject]:
    return list((await db.execute(select(Subject))).scalars().all())


async def create_subject(db: AsyncSession, name: str) -> Subject:
    subject = Subject(name=name)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


async def delete_subject(db: AsyncSession, subject_id: uuid.UUID) -> None:
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise NotFoundError("Subject not found")
    await db.delete(subject)
    await db.commit()
