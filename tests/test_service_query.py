from unittest.mock import AsyncMock, MagicMock, patch

from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.query import QueryFilters
from app.services import query as query_service


async def test_answer_question_no_chunks_returns_fallback(db):
    with patch("app.services.query.embed_question", new_callable=AsyncMock, return_value=[0.1] * 1536):
        response = await query_service.answer_question(db, "What is photosynthesis?", QueryFilters())

    assert "No relevant content" in response.answer
    assert response.sources == []


async def test_answer_question_with_results(db):
    doc = Document(title="Bio Notes", document_type="notes", subject="Biology", level="GCSE")
    db.add(doc)
    await db.flush()
    db.add(Chunk(
        document_id=doc.id,
        content="Photosynthesis converts light energy into glucose.",
        embedding=[0.1] * 1536,
        page_number=1,
        chunk_index=0,
    ))
    await db.commit()

    mock_chat = MagicMock()
    mock_chat.choices = [MagicMock()]
    mock_chat.choices[0].message.content = "Photosynthesis is the process plants use to make food."

    with patch("app.services.query.embed_question", new_callable=AsyncMock, return_value=[0.1] * 1536):
        with patch.object(query_service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_chat):
            response = await query_service.answer_question(db, "What is photosynthesis?", QueryFilters())

    assert "Photosynthesis" in response.answer
    assert len(response.sources) == 1
    assert response.sources[0].title == "Bio Notes"
    assert response.sources[0].page_number == 1


async def test_answer_question_deduplicates_sources(db):
    doc = Document(title="Maths Notes", document_type="notes", subject="Maths", level="GCSE")
    db.add(doc)
    await db.flush()
    # Two chunks on the same page — should produce one source entry
    for i in range(2):
        db.add(Chunk(
            document_id=doc.id,
            content=f"Quadratic formula chunk {i}",
            embedding=[0.1] * 1536,
            page_number=1,
            chunk_index=i,
        ))
    await db.commit()

    mock_chat = MagicMock()
    mock_chat.choices = [MagicMock()]
    mock_chat.choices[0].message.content = "Use the quadratic formula."

    with patch("app.services.query.embed_question", new_callable=AsyncMock, return_value=[0.1] * 1536):
        with patch.object(query_service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_chat):
            response = await query_service.answer_question(db, "How do I solve quadratics?", QueryFilters())

    assert len(response.sources) == 1


async def test_answer_question_applies_filters(db):
    doc = Document(title="Physics Notes", document_type="notes", subject="Physics", level="A-Level")
    db.add(doc)
    await db.flush()
    db.add(Chunk(
        document_id=doc.id,
        content="Newton's second law: F=ma",
        embedding=[0.1] * 1536,
        page_number=1,
        chunk_index=0,
    ))
    await db.commit()

    # Filter for Biology — should find nothing
    with patch("app.services.query.embed_question", new_callable=AsyncMock, return_value=[0.1] * 1536):
        response = await query_service.answer_question(db, "What is Newton's law?", QueryFilters(subject="Biology"))

    assert "No relevant content" in response.answer
