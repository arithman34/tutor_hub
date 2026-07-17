from unittest.mock import AsyncMock, patch

import pytest

from app.services.ingestion import chunk_text, ingest_document


def test_chunk_text_single_chunk():
    chunks = chunk_text("Hello world", page_number=1)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Hello world"
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["chunk_index"] == 0


def test_chunk_text_multiple_chunks():
    text = "a" * 1000
    chunks = chunk_text(text, page_number=2)
    assert len(chunks) > 1
    assert all(c["page_number"] == 2 for c in chunks)
    for i, c in enumerate(chunks):
        assert c["chunk_index"] == i


def test_chunk_text_overlap():
    text = "a" * 1000
    chunks = chunk_text(text, page_number=1)
    # stride = chunk_size - overlap (800 - 100 = 700), so chunks overlap by 100 chars
    assert chunks[0]["content"][-100:] == chunks[1]["content"][:100]


async def test_ingest_document_empty_pdf(db):
    with patch("app.services.ingestion.extract_pages", return_value=[]):
        with pytest.raises(ValueError, match="No text"):
            await ingest_document(
                db,
                file_bytes=b"fake",
                title="Empty Doc",
                document_type="notes",
                subject="Math",
                level="GCSE",
                source_filename="empty.pdf",
            )


async def test_ingest_document_success(db):
    fake_embedding = [0.1] * 1536

    with patch("app.services.ingestion.extract_pages", return_value=[("Some text content here", 1)]):
        with patch("app.services.ingestion.embed_texts", new_callable=AsyncMock, return_value=[fake_embedding]):
            doc = await ingest_document(
                db,
                file_bytes=b"fake",
                title="Test Doc",
                document_type="notes",
                subject="Maths",
                level="GCSE",
                source_filename="test.pdf",
            )

    assert doc.id is not None
    assert doc.title == "Test Doc"
    assert doc.subject == "Maths"


async def test_ingest_document_with_optional_fields(db):
    fake_embedding = [0.0] * 1536

    with patch("app.services.ingestion.extract_pages", return_value=[("Content", 1)]):
        with patch("app.services.ingestion.embed_texts", new_callable=AsyncMock, return_value=[fake_embedding]):
            doc = await ingest_document(
                db,
                file_bytes=b"fake",
                title="Doc With Extras",
                document_type="past_paper",
                subject="Physics",
                level="A-Level",
                source_filename="paper.pdf",
                exam_board="AQA",
            )

    assert doc.exam_board == "AQA"
    assert doc.document_type == "past_paper"
