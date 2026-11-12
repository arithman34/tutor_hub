"""TutorHub AI over the API, sharing its conversation with the web page."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

from .conversation import MAX_QUESTION_LENGTH
from .llm import LLMError
from .models import AssistantUsage

CONVERSATION = "/api/v1/assistant/"
ASK = "/api/v1/assistant/ask"
RESET = "/api/v1/assistant/reset"


def make_user(email="tutor@example.com", limit=5):
    return User.objects.create_user(
        email=email, password="x", first_name="A", last_name="B", assistant_daily_limit=limit
    )


class AssistantApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def used(self):
        return sum(AssistantUsage.objects.filter(user=self.user).values_list("questions", flat=True))

    def test_empty_conversation(self):
        response = self.client.get(CONVERSATION)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["history"], [])
        self.assertEqual(body["allowance"], {"limit": 5, "used": 0, "remaining": 5, "unlimited": False, "exhausted": False})
        self.assertEqual(body["max_question_length"], MAX_QUESTION_LENGTH)
        self.assertTrue(body["examples"])

    @patch("assistant.conversation.agent.answer", return_value="You taught 4 sessions.")
    def test_ask_answers_and_remembers(self, mock_answer):
        response = self.client.post(ASK, {"question": "How many sessions?"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["reply"], "You taught 4 sessions.")
        self.assertEqual(response.json()["allowance"]["used"], 1)
        expected = [
            {"role": "user", "content": "How many sessions?"},
            {"role": "assistant", "content": "You taught 4 sessions."},
        ]
        self.assertEqual(response.json()["history"], expected)
        self.assertEqual(self.client.get(CONVERSATION).json()["history"], expected)

        self.client.post(ASK, {"question": "And last month?"}, format="json")
        self.assertEqual(mock_answer.call_args.kwargs["history"], expected)

    @patch("assistant.conversation.agent.answer")
    def test_exhausted_allowance_is_429_without_calling_model(self, mock_answer):
        self.user.assistant_daily_limit = 0
        self.user.save()
        response = self.client.post(ASK, {"question": "Hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertTrue(response.json()["allowance"]["exhausted"])
        mock_answer.assert_not_called()

    @patch("assistant.conversation.agent.answer", side_effect=LLMError("down"))
    def test_provider_failure_is_502_and_refunded(self, _mock_answer):
        response = self.client.post(ASK, {"question": "Hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(self.used(), 0)
        self.assertEqual(self.client.get(CONVERSATION).json()["history"], [])

    @patch("assistant.conversation.agent.answer")
    def test_too_long_or_blank_question_is_rejected_without_charge(self, mock_answer):
        for question in ("x" * (MAX_QUESTION_LENGTH + 1), "   "):
            with self.subTest(length=len(question)):
                response = self.client.post(ASK, {"question": question}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_answer.assert_not_called()
        self.assertEqual(self.used(), 0)

    @patch("assistant.conversation.agent.answer", return_value="Hello")
    def test_reset_clears_history(self, _mock_answer):
        self.client.post(ASK, {"question": "Hi"}, format="json")
        self.assertEqual(self.client.post(RESET).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(CONVERSATION).json()["history"], [])

    def test_requires_authentication(self):
        client = APIClient()
        self.assertEqual(client.get(CONVERSATION).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(client.post(ASK, {"question": "Hi"}, format="json").status_code, status.HTTP_401_UNAUTHORIZED)


class CookieConversationTests(APITestCase):
    """The browser app's case: signed in by cookie, so CSRF applies, and the
    conversation is kept in the session between requests."""

    @patch("assistant.conversation.agent.answer", return_value="From the API")
    def test_asking_needs_the_csrf_token_and_the_answer_is_kept(self, _mock_answer):
        user = make_user()
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]

        self.assertEqual(client.post(ASK, {"question": "Hi"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        response = client.post(ASK, {"question": "Hi"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = client.get(CONVERSATION).json()["history"]
        self.assertEqual([message["content"] for message in messages], ["Hi", "From the API"])
