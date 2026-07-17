from uuid import UUID

from pydantic import BaseModel


class QueryFilters(BaseModel):
    document_type: str | None = None
    subject: str | None = None
    level: str | None = None
    exam_board: str | None = None
    student_id: UUID | None = None


class SourceChunk(BaseModel):
    document_id: UUID
    title: str
    page_number: int | None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
