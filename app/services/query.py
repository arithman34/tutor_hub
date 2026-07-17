from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.query import QueryFilters, QueryResponse, SourceChunk

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_question(question: str) -> list[float]:
    response = await client.embeddings.create(model=settings.embedding_model, input=question)
    return response.data[0].embedding


async def answer_question(
    session: AsyncSession,
    question: str,
    filters: QueryFilters,
) -> QueryResponse:
    query_embedding = await embed_question(question)

    stmt = (
        select(Chunk)
        .join(Chunk.document)
        .options(joinedload(Chunk.document))
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(settings.top_k)
    )

    if filters.document_type:
        stmt = stmt.where(Document.document_type == filters.document_type)
    if filters.subject:
        stmt = stmt.where(Document.subject == filters.subject)
    if filters.level:
        stmt = stmt.where(Document.level == filters.level)
    if filters.exam_board:
        stmt = stmt.where(Document.exam_board == filters.exam_board)
    if filters.student_id:
        stmt = stmt.where(Document.student_id == filters.student_id)

    chunks = (await session.execute(stmt)).scalars().all()

    if not chunks:
        return QueryResponse(answer="No relevant content found for your question.", sources=[])

    context = "\n\n".join(
        f"[Source: {chunk.document.title}, Page {chunk.page_number}]\n{chunk.content}"
        for chunk in chunks
    )

    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful tutor assistant. Answer the question using only "
                    "the context provided. If the answer is not in the context, say so. "
                    "Be concise and accurate."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )

    answer = response.choices[0].message.content

    seen: set[tuple] = set()
    sources = []
    for chunk in chunks:
        key = (chunk.document_id, chunk.page_number)
        if key not in seen:
            seen.add(key)
            sources.append(SourceChunk(
                document_id=chunk.document_id,
                title=chunk.document.title,
                page_number=chunk.page_number,
            ))

    return QueryResponse(answer=answer, sources=sources)
