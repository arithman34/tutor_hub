from unittest.mock import patch

from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from assistant.llm import LLMError
from assistant.models import AssistantUsage
from assistant.quota import get_allowance, uk_today

ANSWER = "web.assistant_views.agent.answer"


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class AssistantPageTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        login(self.client, self.tutor)

    def test_unauthenticated_redirects_to_login(self):
        for method, path in (("get", "/assistant"), ("post", "/assistant/ask"), ("post", "/assistant/reset")):
            with self.subTest(path=path):
                response = getattr(Client(), method)(path)
                self.assertRedirects(response, "/login", fetch_redirect_response=False)

    def test_empty_page_shows_examples_and_allowance(self):
        response = self.client.get("/assistant")
        self.assertContains(response, "TutorHub AI")
        self.assertContains(response, "Does any payee owe me money?")
        self.assertContains(response, "1 of 1 question left today")
        self.assertNotContains(response, "New chat")

    def test_sidebar_links_to_tutorhub_ai_not_documents(self):
        response = self.client.get("/dashboard")
        self.assertContains(response, 'href="/assistant"')
        self.assertNotContains(response, 'href="/documents"')

    def test_unlimited_account(self):
        self.tutor.assistant_daily_limit = None
        self.tutor.save()
        self.assertContains(self.client.get("/assistant"), "Unlimited questions")

    def test_exhausted_allowance_disables_the_form(self):
        AssistantUsage.objects.create(user=self.tutor, day=uk_today(), questions=1)
        response = self.client.get("/assistant")
        self.assertContains(response, "No questions left today")
        self.assertContains(response, "Come back tomorrow")


class AssistantAskTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com", assistant_daily_limit=3)
        login(self.client, self.tutor)

    @patch(ANSWER, return_value="Lok has had 4 sessions.")
    def test_ask_answers_and_shows_conversation(self, answer):
        response = self.client.post("/assistant/ask", {"question": "  How many sessions has Lok had?  "})
        self.assertRedirects(response, "/assistant", fetch_redirect_response=False)

        answer.assert_called_once_with(self.tutor, "How many sessions has Lok had?", history=[])
        page = self.client.get("/assistant")
        self.assertContains(page, "How many sessions has Lok had?")
        self.assertContains(page, "Lok has had 4 sessions.")
        self.assertContains(page, "New chat")
        self.assertContains(page, "2 of 3 questions left today")

    @patch(ANSWER, side_effect=["First answer.", "Second answer."])
    def test_follow_up_gets_the_history(self, answer):
        self.client.post("/assistant/ask", {"question": "First?"})
        self.client.post("/assistant/ask", {"question": "Second?"})
        self.assertEqual(
            answer.call_args.kwargs["history"],
            [{"role": "user", "content": "First?"}, {"role": "assistant", "content": "First answer."}],
        )

    @patch(ANSWER, return_value="<script>alert(1)</script>")
    def test_answers_are_escaped(self, answer):
        self.client.post("/assistant/ask", {"question": "<b>hi</b>"})
        page = self.client.get("/assistant")
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertContains(page, "&lt;b&gt;hi&lt;/b&gt;")

    @patch(ANSWER)
    def test_blank_question_is_ignored(self, answer):
        response = self.client.post("/assistant/ask", {"question": "   "})
        self.assertRedirects(response, "/assistant", fetch_redirect_response=False)
        answer.assert_not_called()
        self.assertEqual(get_allowance(self.tutor).used, 0)

    @patch(ANSWER)
    def test_too_long_question_is_refused_and_kept(self, answer):
        question = "x" * 1001
        response = self.client.post("/assistant/ask", {"question": question})
        self.assertRedirects(response, "/assistant?flash=too_long", fetch_redirect_response=False)
        answer.assert_not_called()
        self.assertEqual(get_allowance(self.tutor).used, 0)
        self.assertContains(self.client.get("/assistant?flash=too_long"), "at most 1000 characters")

    @patch(ANSWER)
    def test_limit_reached_does_not_call_the_model(self, answer):
        AssistantUsage.objects.create(user=self.tutor, day=uk_today(), questions=3)
        response = self.client.post("/assistant/ask", {"question": "One more?"})
        self.assertRedirects(response, "/assistant?flash=limit", fetch_redirect_response=False)
        answer.assert_not_called()

        page = self.client.get("/assistant?flash=limit")
        self.assertContains(page, "reached today's TutorHub AI limit")
        self.assertContains(page, "One more?")

    @patch(ANSWER, side_effect=LLMError("down"))
    def test_provider_error_refunds_and_keeps_the_question(self, answer):
        with self.assertLogs("web.assistant_views", level="ERROR"):
            response = self.client.post("/assistant/ask", {"question": "Who owes me?"})
        self.assertRedirects(response, "/assistant?flash=error", fetch_redirect_response=False)
        self.assertEqual(get_allowance(self.tutor).used, 0)

        page = self.client.get("/assistant?flash=error")
        self.assertContains(page, "wasn't counted")
        self.assertContains(page, "Who owes me?")
        self.assertNotContains(self.client.get("/assistant"), "Who owes me?")

    @patch(ANSWER, side_effect=RuntimeError("bug"))
    def test_unexpected_error_still_refunds(self, answer):
        with self.assertRaises(RuntimeError):
            self.client.post("/assistant/ask", {"question": "Who owes me?"})
        self.assertEqual(get_allowance(self.tutor).used, 0)

    @patch(ANSWER, return_value="Hi.")
    def test_reset_clears_the_conversation(self, answer):
        self.client.post("/assistant/ask", {"question": "Hello?"})
        response = self.client.post("/assistant/reset")
        self.assertRedirects(response, "/assistant", fetch_redirect_response=False)
        self.assertNotContains(self.client.get("/assistant"), "Hello?")
        self.assertEqual(get_allowance(self.tutor).used, 1)

    @patch(ANSWER, return_value="Private answer.")
    def test_conversation_is_not_shown_to_another_account_on_the_same_browser(self, answer):
        self.client.post("/assistant/ask", {"question": "Private question?"})
        login(self.client, make_user("other@example.com"))
        page = self.client.get("/assistant")
        self.assertNotContains(page, "Private question?")
        self.assertNotContains(page, "Private answer.")

    def test_get_is_not_allowed_on_actions(self):
        self.assertEqual(self.client.get("/assistant/ask").status_code, 405)
        self.assertEqual(self.client.get("/assistant/reset").status_code, 405)


class AssistantCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = make_user("tutor@example.com")
        login(self.client, self.tutor)

    def _csrf_token(self):
        self.client.get("/assistant")
        return self.client.cookies["csrftoken"].value

    @patch(ANSWER, return_value="Hi.")
    def test_ask_form_includes_working_csrf_token(self, answer):
        response = self.client.post("/assistant/ask", {"question": "Hello?", "csrfmiddlewaretoken": self._csrf_token()})
        self.assertRedirects(response, "/assistant", fetch_redirect_response=False)

    @patch(ANSWER)
    def test_ask_without_token_is_rejected(self, answer):
        self.assertEqual(self.client.post("/assistant/ask", {"question": "Hello?"}).status_code, 403)
        answer.assert_not_called()

    def test_reset_form_includes_working_csrf_token(self):
        response = self.client.post("/assistant/reset", {"csrfmiddlewaretoken": self._csrf_token()})
        self.assertRedirects(response, "/assistant", fetch_redirect_response=False)

    def test_reset_without_token_is_rejected(self):
        self.assertEqual(self.client.post("/assistant/reset").status_code, 403)


class AssistantConversationTests(TestCase):
    """Runs the real view and agent loop with only the model faked."""

    def setUp(self):
        self.tutor = make_user("tutor@example.com", assistant_daily_limit=None)
        login(self.client, self.tutor)

    def test_follow_up_question_is_sent_with_the_earlier_exchange(self):
        from assistant.llm import LLMReply

        seen = []

        class RecordingClient:
            def chat(self, system, messages, tools, timeout):
                seen.append(list(messages))
                return LLMReply(text="Mei Chan owes £40.00." if len(seen) == 1 else "No one else.")

        with patch("assistant.agent.get_client", RecordingClient):
            self.client.post("/assistant/ask", {"question": "Does any payee owe me money?"})
            self.client.post("/assistant/ask", {"question": "Anyone else?"})

        self.assertEqual(
            seen[1],
            [
                {"role": "user", "content": "Does any payee owe me money?"},
                {"role": "assistant", "content": "Mei Chan owes £40.00."},
                {"role": "user", "content": "Anyone else?"},
            ],
        )
        self.assertContains(self.client.get("/assistant"), "No one else.")


class DocumentsRemovedTests(TestCase):
    def test_documents_pages_and_api_are_gone(self):
        login(self.client, make_user("tutor@example.com"))
        for path in ("/documents", "/api/v1/documents/", "/api/v1/query"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
