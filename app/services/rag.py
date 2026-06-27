import httpx

from app.core.config import settings


class RAGServiceError(Exception):
    pass


def _client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.rag_api_url,
        headers={"X-API-Key": settings.rag_api_key},
        timeout=timeout,
    )


async def list_documents(
    document_type: str | None = None,
    subject: str | None = None,
    level: str | None = None,
    exam_board: str | None = None,
) -> list[dict]:
    params: dict[str, str] = {}
    if document_type:
        params["document_type"] = document_type
    if subject:
        params["subject"] = subject
    if level:
        params["level"] = level
    if exam_board:
        params["exam_board"] = exam_board

    async with _client() as client:
        resp = await client.get("/api/v1/documents", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])


async def upload_document(
    file_bytes: bytes,
    filename: str,
    title: str,
    document_type: str,
    subject: str,
    level: str,
    exam_board: str | None = None,
) -> dict:
    async with _client(timeout=60.0) as client:
        files = {"file": (filename, file_bytes, "application/pdf")}
        data: dict[str, str] = {
            "title": title,
            "document_type": document_type,
            "subject": subject,
            "level": level,
        }
        if exam_board:
            data["exam_board"] = exam_board
        resp = await client.post("/api/v1/documents", files=files, data=data)
        resp.raise_for_status()
        return resp.json()


async def delete_document(document_id: str) -> None:
    async with _client() as client:
        resp = await client.delete(f"/api/v1/documents/{document_id}")
        resp.raise_for_status()


async def query_documents(
    question: str,
    document_type: str | None = None,
    subject: str | None = None,
    level: str | None = None,
    exam_board: str | None = None,
) -> dict:
    filters: dict[str, str | None] = {
        "document_type": document_type,
        "subject": subject,
        "level": level,
        "exam_board": exam_board,
    }
    async with _client(timeout=60.0) as client:
        resp = await client.post(
            "/api/v1/query",
            json={"question": question, "filters": filters},
        )
        resp.raise_for_status()
        return resp.json()
