import io
import uuid

import pdfplumber
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document

client = AsyncOpenAI(api_key=settings.openai_api_key)


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
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append({"content": text[start:end], "page_number": page_number, "chunk_index": index})
        start += size - overlap
        index += 1
    return chunks


async def embed_texts(texts: list[str]) -> list[list[float]]:
    response = await client.embeddings.create(model=settings.embedding_model, input=texts)
    return [item.embedding for item in response.data]


async def ingest_document(
    session: AsyncSession,
    file_bytes: bytes,
    title: str,
    document_type: str,
    subject: str,
    level: str,
    source_filename: str,
    exam_board: str | None = None,
    student_id: uuid.UUID | None = None,
) -> Document:
    pages = extract_pages(file_bytes)
    if not pages:
        raise ValueError("No text could be extracted from this PDF.")

    raw_chunks = []
    for text, page_number in pages:
        raw_chunks.extend(chunk_text(text, page_number))

    embeddings = await embed_texts([c["content"] for c in raw_chunks])

    document = Document(
        title=title,
        document_type=document_type,
        subject=subject,
        level=level,
        exam_board=exam_board,
        student_id=student_id,
        source_url=source_filename,
    )
    session.add(document)
    await session.flush()

    for i, (raw, embedding) in enumerate(zip(raw_chunks, embeddings)):
        session.add(Chunk(
            document_id=document.id,
            content=raw["content"],
            embedding=embedding,
            page_number=raw["page_number"],
            chunk_index=i,
        ))

    await session.commit()
    await session.refresh(document)
    return document
