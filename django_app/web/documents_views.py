import uuid

from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from rag import services
from rag.models import Document

from .auth import login_required


def _list_documents():
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
        for d in Document.objects.order_by("-uploaded_at")
    ]


@login_required
def documents_page(request):
    user = request.user
    return render(
        request,
        "documents/index.html",
        {
            "user": user,
            "active_page": "documents",
            "active_tab": "documents",
            "documents": _list_documents(),
            "flash": request.GET.get("flash"),
        },
    )


@login_required
@require_http_methods(["POST"])
def upload_document(request):
    file = request.FILES.get("file")
    try:
        services.ingest_document(
            file_bytes=file.read(),
            title=request.POST["title"],
            document_type=request.POST["document_type"],
            subject=request.POST["subject"],
            level=request.POST["level"],
            source_filename=file.name if file else "document.pdf",
            exam_board=request.POST.get("exam_board") or None,
        )
    except Exception:
        return redirect("/documents?flash=upload_error")

    return redirect("/documents?flash=uploaded")


@login_required
@require_http_methods(["POST"])
def delete_document(request, document_id):
    try:
        Document.objects.filter(id=uuid.UUID(str(document_id))).delete()
    except (ValueError, TypeError):
        return redirect("/documents?flash=delete_error")

    return redirect("/documents?flash=deleted")


@login_required
@require_http_methods(["POST"])
def query_documents(request):
    user = request.user
    question = request.POST.get("question", "")
    subject = request.POST.get("subject", "")
    level = request.POST.get("level", "")
    document_type = request.POST.get("document_type", "")
    exam_board = request.POST.get("exam_board", "")

    answer = None
    sources: list = []
    query_error = None

    try:
        result = services.answer_question(
            question,
            {
                "subject": subject or None,
                "level": level or None,
                "document_type": document_type or None,
                "exam_board": exam_board or None,
            },
        )
        answer = result["answer"]
        sources = result["sources"]
    except Exception:
        query_error = "Could not get an answer. Please try again."

    return render(
        request,
        "documents/index.html",
        {
            "user": user,
            "active_page": "documents",
            "active_tab": "query",
            "documents": _list_documents(),
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
