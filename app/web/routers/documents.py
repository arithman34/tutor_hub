from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.models.user import User
from app.services import rag as rag_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(prefix="/documents", tags=["Documents"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard")

    documents: list[dict] = []
    service_error: str | None = None
    try:
        documents = await rag_service.list_documents()
    except Exception:
        service_error = "Could not reach the RAG service. Check that it is running and RAG_API_URL/RAG_API_KEY are set."

    flash = request.query_params.get("flash")
    return templates.TemplateResponse(
        request,
        "documents/index.html",
        {
            "user": user,
            "active_page": "documents",
            "active_tab": "documents",
            "documents": documents,
            "service_error": service_error,
            "flash": flash,
        },
    )


@router.post("/upload")
async def upload_document(
    request: Request,
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
        await rag_service.upload_document(
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf",
            title=title,
            document_type=document_type,
            subject=subject,
            level=level,
            exam_board=exam_board or None,
        )
    except Exception:
        return RedirectResponse("/documents?flash=upload_error", status_code=303)

    return RedirectResponse("/documents?flash=uploaded", status_code=303)


@router.post("/{document_id}/delete")
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_tutor:
        return RedirectResponse("/dashboard", status_code=303)

    try:
        await rag_service.delete_document(document_id)
    except Exception:
        return RedirectResponse("/documents?flash=delete_error", status_code=303)

    return RedirectResponse("/documents?flash=deleted", status_code=303)


@router.post("/query", response_class=HTMLResponse)
async def query_documents(
    request: Request,
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
    sources: list[dict] = []
    query_error: str | None = None
    documents: list[dict] = []

    try:
        result = await rag_service.query_documents(
            question=question,
            subject=subject or None,
            level=level or None,
            document_type=document_type or None,
            exam_board=exam_board or None,
        )
        answer = result.get("answer")
        sources = result.get("sources", [])
    except Exception:
        query_error = "Could not get an answer. Check that the RAG service is running."

    try:
        documents = await rag_service.list_documents()
    except Exception:
        pass

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
