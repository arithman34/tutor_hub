from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from rag.models import Document


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class DocumentsPageTests(TestCase):
    def test_tutor_sees_documents(self):
        tutor = make_user("tutor@example.com")
        Document.objects.create(title="Algebra Basics", document_type="worksheet", subject="maths", level="GCSE")
        login(self.client, tutor)
        response = self.client.get("/documents")
        self.assertContains(response, "Algebra Basics")

    def test_admin_redirected_away(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/documents")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/documents")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_flash_uploaded_shows_success_message(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/documents", {"flash": "uploaded"})
        self.assertContains(response, "Document uploaded and indexed.")


class UploadDocumentTests(TestCase):
    @patch("rag.services.embed_texts")
    @patch("rag.services.extract_pages")
    def test_tutor_can_upload_document(self, mock_extract_pages, mock_embed_texts):
        mock_extract_pages.return_value = [("Some text.", 1)]
        mock_embed_texts.return_value = [[0.0] * 1536]

        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(
            "/documents/upload",
            {"file": upload, "title": "Notes", "document_type": "worksheet", "subject": "maths", "level": "GCSE"},
        )
        self.assertRedirects(response, "/documents?flash=uploaded", fetch_redirect_response=False)
        self.assertEqual(Document.objects.count(), 1)

    def test_admin_cannot_upload(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(
            "/documents/upload",
            {"file": upload, "title": "Notes", "document_type": "worksheet", "subject": "maths", "level": "GCSE"},
        )
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertEqual(Document.objects.count(), 0)

    @patch("rag.services.extract_pages")
    def test_ingestion_failure_redirects_with_error_flash(self, mock_extract_pages):
        mock_extract_pages.return_value = []

        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(
            "/documents/upload",
            {"file": upload, "title": "Notes", "document_type": "worksheet", "subject": "maths", "level": "GCSE"},
        )
        self.assertRedirects(response, "/documents?flash=upload_error", fetch_redirect_response=False)
        self.assertEqual(Document.objects.count(), 0)


class DeleteDocumentTests(TestCase):
    def test_tutor_can_delete(self):
        tutor = make_user("tutor@example.com")
        document = Document.objects.create(title="Notes", document_type="worksheet", subject="maths", level="GCSE")
        login(self.client, tutor)
        response = self.client.post(f"/documents/{document.id}/delete")
        self.assertRedirects(response, "/documents?flash=deleted", fetch_redirect_response=False)
        self.assertFalse(Document.objects.filter(id=document.id).exists())

    def test_admin_cannot_delete(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        document = Document.objects.create(title="Notes", document_type="worksheet", subject="maths", level="GCSE")
        login(self.client, admin)
        response = self.client.post(f"/documents/{document.id}/delete")
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)
        self.assertTrue(Document.objects.filter(id=document.id).exists())


class QueryDocumentsTests(TestCase):
    def test_tutor_gets_answer_rendered_on_page(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        with patch("rag.services.answer_question") as mock_answer:
            mock_answer.return_value = {"answer": "Photosynthesis is how plants make food.", "sources": []}
            response = self.client.post("/documents/query", {"question": "What is photosynthesis?"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Photosynthesis is how plants make food.")

    def test_query_failure_shows_error_message(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        with patch("rag.services.answer_question", side_effect=RuntimeError("boom")):
            response = self.client.post("/documents/query", {"question": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not get an answer")

    def test_admin_redirected_away(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.post("/documents/query", {"question": "x"})
        self.assertRedirects(response, "/dashboard", fetch_redirect_response=False)


class DocumentsFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = make_user("tutor@example.com")
        self.document = Document.objects.create(title="Notes", document_type="worksheet", subject="maths", level="GCSE")
        login(self.client, self.tutor)

    def _csrf_token(self):
        self.client.get("/documents")
        return self.client.cookies["csrftoken"].value

    @patch("rag.services.embed_texts")
    @patch("rag.services.extract_pages")
    def test_upload_form_includes_working_csrf_token(self, mock_extract_pages, mock_embed_texts):
        mock_extract_pages.return_value = [("Some text.", 1)]
        mock_embed_texts.return_value = [[0.0] * 1536]
        token = self._csrf_token()
        upload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(
            "/documents/upload",
            {
                "file": upload,
                "title": "Notes",
                "document_type": "worksheet",
                "subject": "maths",
                "level": "GCSE",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_form_includes_working_csrf_token(self):
        token = self._csrf_token()
        response = self.client.post(f"/documents/{self.document.id}/delete", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_query_form_includes_working_csrf_token(self):
        token = self._csrf_token()
        with patch("rag.services.answer_question", return_value={"answer": "x", "sources": []}):
            response = self.client.post("/documents/query", {"question": "x", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 200)
