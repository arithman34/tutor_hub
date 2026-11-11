import unittest
from unittest.mock import MagicMock, patch

from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from . import services
from .models import Chunk, Document

requires_postgres = unittest.skipUnless(
    connection.vendor == "postgresql", "pgvector cosine-distance ordering needs a real Postgres + pgvector backend"
)


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class ChunkTextTests(APITestCase):
    def test_chunk_text_splits_with_overlap(self):
        text = "a" * 2000
        chunks = services.chunk_text(text, page_number=1)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["page_number"], 1)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[1]["chunk_index"], 1)

    def test_chunk_text_single_chunk_for_short_text(self):
        chunks = services.chunk_text("short text", page_number=2)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["content"], "short text")


class IngestDocumentTests(APITestCase):
    @patch("rag.services.embed_texts")
    @patch("rag.services.extract_pages")
    def test_ingest_document_creates_document_and_chunks(self, mock_extract_pages, mock_embed_texts):
        mock_extract_pages.return_value = [("Some page text.", 1)]
        mock_embed_texts.return_value = [[0.0] * 1536]

        document = services.ingest_document(
            file_bytes=b"irrelevant-because-extract_pages-is-mocked",
            title="Algebra Basics",
            document_type="worksheet",
            subject="maths",
            level="GCSE",
            source_filename="algebra.pdf",
        )

        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(document.title, "Algebra Basics")
        self.assertEqual(Chunk.objects.filter(document=document).count(), 1)

    @patch("rag.services.extract_pages")
    def test_ingest_document_raises_when_no_text_extracted(self, mock_extract_pages):
        mock_extract_pages.return_value = []
        with self.assertRaises(ValueError):
            services.ingest_document(
                file_bytes=b"irrelevant",
                title="Empty",
                document_type="worksheet",
                subject="maths",
                level="GCSE",
                source_filename="empty.pdf",
            )


class DocumentViewPermissionTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.url = reverse("document-list")

    def test_tutor_can_list_documents(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_list_documents(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("rag.services.embed_texts")
    @patch("rag.services.extract_pages")
    def test_tutor_can_upload_document(self, mock_extract_pages, mock_embed_texts):
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_extract_pages.return_value = [("Some text.", 1)]
        mock_embed_texts.return_value = [[0.0] * 1536]

        self.client.force_authenticate(self.tutor)
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(
            self.url,
            {"file": upload, "title": "Notes", "document_type": "worksheet", "subject": "maths", "level": "GCSE"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 1)


class QueryViewTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.url = reverse("rag-query")

    @requires_postgres
    def test_query_returns_no_results_message_when_no_chunks_exist(self):
        self.client.force_authenticate(self.tutor)
        with patch("rag.services.embed_texts", return_value=[[0.0] * 1536]):
            response = self.client.post(self.url, {"question": "What is photosynthesis?"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["answer"], "No relevant content found for your question.")
        self.assertEqual(response.data["sources"], [])

    @requires_postgres
    @patch("rag.services.get_client")
    @patch("rag.services.embed_texts")
    def test_query_returns_answer_with_sources_from_matching_chunks(self, mock_embed_texts, mock_get_client):
        mock_embed_texts.return_value = [[0.0] * 1536]
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Photosynthesis is how plants make food."
        mock_get_client.return_value.chat.completions.create.return_value = mock_response

        document = Document.objects.create(title="Biology Notes", document_type="worksheet", subject="biology", level="GCSE")
        Chunk.objects.create(document=document, content="Plants use sunlight...", embedding=[0.0] * 1536, page_number=1, chunk_index=0)

        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, {"question": "What is photosynthesis?"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["answer"], "Photosynthesis is how plants make food.")
        self.assertEqual(len(response.data["sources"]), 1)
