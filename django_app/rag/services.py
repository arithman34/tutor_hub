import io

import pdfplumber
from django.conf import settings
from openai import OpenAI

from .models import Chunk, Document

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def extract_pages(file_bytes: bytes) -> list[tuple[str, int]]:
    pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((text, i))
    return pages


def chunk_text(text: str, page_number: int) -> list[dict]:
    chunks = []
    start = 0
    index = 0
    size = settings.RAG_CHUNK_SIZE
    overlap = settings.RAG_CHUNK_OVERLAP
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append({"content": text[start:end], "page_number": page_number, "chunk_index": index})
        start += size - overlap
        index += 1
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    response = get_client().embeddings.create(model=settings.RAG_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def ingest_document(
    file_bytes: bytes,
    title: str,
    document_type: str,
    subject: str,
    level: str,
    source_filename: str,
    exam_board: str | None = None,
    student_id=None,
) -> Document:
    pages = extract_pages(file_bytes)
    if not pages:
        raise ValueError("No text could be extracted from this PDF.")

    raw_chunks = []
    for text, page_number in pages:
        raw_chunks.extend(chunk_text(text, page_number))

    embeddings = embed_texts([c["content"] for c in raw_chunks])

    document = Document.objects.create(
        title=title,
        document_type=document_type,
        subject=subject,
        level=level,
        exam_board=exam_board,
        student_id=student_id,
        source_url=source_filename,
    )

    Chunk.objects.bulk_create(
        [
            Chunk(
                document=document,
                content=raw["content"],
                embedding=embedding,
                page_number=raw["page_number"],
                chunk_index=i,
            )
            for i, (raw, embedding) in enumerate(zip(raw_chunks, embeddings))
        ]
    )
    return document


SYSTEM_PROMPT = (
    "You are a helpful tutor assistant. Answer the question using only "
    "the context provided. If the answer is not in the context, say so. "
    "Be concise and accurate. The answer is displayed as plain text, so never "
    "use markdown: no ** or __ for bold, no # headings. For lists, start each "
    "item on a new line with a dash. Write mathematical expressions in LaTeX "
    "between \\( and \\) so they render as equations."
)


def answer_question(question: str, filters: dict) -> dict:
    from pgvector.django import CosineDistance

    query_embedding = embed_texts([question])[0]

    qs = Chunk.objects.select_related("document")
    if filters.get("document_type"):
        qs = qs.filter(document__document_type=filters["document_type"])
    if filters.get("subject"):
        qs = qs.filter(document__subject=filters["subject"])
    if filters.get("level"):
        qs = qs.filter(document__level=filters["level"])
    if filters.get("exam_board"):
        qs = qs.filter(document__exam_board=filters["exam_board"])
    if filters.get("student_id"):
        qs = qs.filter(document__student_id=filters["student_id"])

    chunks = list(qs.order_by(CosineDistance("embedding", query_embedding))[: settings.RAG_TOP_K])

    if not chunks:
        return {"answer": "No relevant content found for your question.", "sources": []}

    context = "\n\n".join(f"[Source: {chunk.document.title}, Page {chunk.page_number}]\n{chunk.content}" for chunk in chunks)

    response = get_client().chat.completions.create(
        model=settings.RAG_CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    answer = response.choices[0].message.content

    seen = set()
    sources = []
    for chunk in chunks:
        key = (chunk.document_id, chunk.page_number)
        if key not in seen:
            seen.add(key)
            sources.append({"document_id": str(chunk.document_id), "title": chunk.document.title, "page_number": chunk.page_number})

    return {"answer": answer, "sources": sources}
