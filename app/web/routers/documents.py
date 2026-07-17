import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.query import QueryFilters
from app.services.ingestion import ingest_document
from app.services.query import answer_question
from app.web.deps import get_current_user_from_cookie

router = APIRouter(prefix="/documents", tags=["Documents"])
templates = Jinja2Templates(directory="templates")


async def _list_documents(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Document).order_by(Document.uploaded_at.desc()))).scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "document_type": d.document_type,
            "subject": d.subject,
            "level": d.level,
            "exam_board": d.exam_board,
            "uploaded_at": d.uploaded_at.strftime("%Y-%m-%d"),
        }
        for d in rows
    ]


@router.get("", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard")

    documents = await _list_documents(db)
    flash = request.query_params.get("flash")
    return templates.TemplateResponse(
        request,
        "documents/index.html",
        {
            "user": user,
            "active_page": "documents",
            "active_tab": "documents",
            "documents": documents,
            "flash": flash,
        },
    )


@router.post("/upload")
async def upload_document(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    subject: str = Form(...),
    level: str = Form(...),
    exam_board: str = Form(""),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard", status_code=303)

    file_bytes = await file.read()
    try:
        await ingest_document(
            session=db,
            file_bytes=file_bytes,
            title=title,
            document_type=document_type,
            subject=subject,
            level=level,
            source_filename=file.filename or "document.pdf",
            exam_board=exam_board or None,
        )
    except Exception as e:
        logger.exception("Document upload failed: %s", e)
        return RedirectResponse("/documents?flash=upload_error", status_code=303)

    return RedirectResponse("/documents?flash=uploaded", status_code=303)


@router.post("/{document_id}/delete")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard", status_code=303)

    try:
        doc = (await db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )).scalar_one_or_none()
        if doc:
            await db.delete(doc)
            await db.commit()
    except Exception:
        return RedirectResponse("/documents?flash=delete_error", status_code=303)

    return RedirectResponse("/documents?flash=deleted", status_code=303)


@router.post("/query", response_class=HTMLResponse)
async def query_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
    question: str = Form(...),
    subject: str = Form(""),
    level: str = Form(""),
    document_type: str = Form(""),
    exam_board: str = Form(""),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard", status_code=303)

    answer: str | None = None
    sources: list = []
    query_error: str | None = None

    try:
        filters = QueryFilters(
            subject=subject or None,
            level=level or None,
            document_type=document_type or None,
            exam_board=exam_board or None,
        )
        result = await answer_question(session=db, question=question, filters=filters)
        answer = result.answer
        sources = [s.model_dump() for s in result.sources]
    except Exception:
        query_error = "Could not get an answer. Please try again."

    documents = await _list_documents(db)

    return templates.TemplateResponse(
        request,
        "documents/index.html",
        {
            "user": user,
            "active_page": "documents",
            "active_tab": "query",
            "documents": documents,
            "question": question,
            "subject": subject,
            "level": level,
            "document_type": document_type,
            "exam_board": exam_board,
            "answer": answer,
            "sources": sources,
            "query_error": query_error,
        },
    )
