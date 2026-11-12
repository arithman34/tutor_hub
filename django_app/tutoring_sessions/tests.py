from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from students.models import Student

from .models import Session


def make_user(email):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


class SessionModelTests(APITestCase):
    def test_minutes_computed_from_start_and_end(self):
        tutor = make_user("tutor@example.com")
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        now = timezone.now()
        session = Session.objects.create(
            user=tutor,
            student=student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(minutes=45),
        )
        self.assertEqual(session.minutes, 45)


class SessionCreateTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        self.url = reverse("session-list")
        self.now = timezone.now()

    def _payload(self, **overrides):
        payload = {
            "student": str(self.student.id),
            "session_date": self.now.isoformat(),
            "session_start_time": self.now.isoformat(),
            "session_end_time": (self.now + timedelta(minutes=30)).isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_cannot_create_session_for_another_accounts_student(self):
        other = make_user("other@example.com")
        self.client.force_authenticate(other)
        response = self.client.post(self.url, self._payload())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Session.objects.exists())

    def test_authenticated_user_creates_session_for_self(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.post(self.url, self._payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Session.objects.get().user, self.tutor)

    def test_end_before_start_is_rejected(self):
        self.client.force_authenticate(self.tutor)
        bad_payload = self._payload(session_end_time=(self.now - timedelta(minutes=5)).isoformat())
        response = self.client.post(self.url, bad_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create(self):
        response = self.client.post(self.url, self._payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SessionAccessTests(APITestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")
        now = timezone.now()
        self.session = Session.objects.create(
            user=self.tutor,
            student=self.student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(minutes=30),
        )
        self.detail_url = reverse("session-detail", args=[self.session.id])

    def test_owner_can_retrieve(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_tutor_gets_404(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.patch(self.detail_url, {"work_covered": "fractions"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["work_covered"], "fractions")

    def test_other_tutor_cannot_update(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.patch(self.detail_url, {"work_covered": "fractions"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_delete(self):
        self.client.force_authenticate(self.tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_tutor_cannot_delete(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Session.objects.filter(id=self.session.id).exists())

    def test_list_only_shows_own_sessions(self):
        self.client.force_authenticate(self.other_tutor)
        response = self.client.get(reverse("session-list"))
        self.assertEqual(response.data["count"], 0)

        self.client.force_authenticate(self.tutor)
        response = self.client.get(reverse("session-list"))
        self.assertEqual(response.data["count"], 1)

    def test_cannot_move_session_to_another_accounts_student(self):
        foreign_student = Student.objects.create(user=self.other_tutor, first_name="Pat", last_name="Jones")
        self.client.force_authenticate(self.tutor)
        response = self.client.patch(self.detail_url, {"student": str(foreign_student.id)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.session.refresh_from_db()
        self.assertEqual(self.session.student, self.student)


class ZoomParseApiTests(APITestCase):
    URL = "/api/v1/sessions/zoom-parse/"

    def setUp(self):
        self.user = User.objects.create_user(email="zoom@example.com", password="x", first_name="A", last_name="B")
        self.client.force_authenticate(self.user)

    def test_returns_parsed_fields(self):
        from tutoring_sessions.zoom import ParsedSession

        parsed = ParsedSession("fractions", "- homework", "- mark", "decimals", "fractions, maths")
        with patch("tutoring_sessions.views.zoom.parse_zoom_summary", return_value=parsed) as mock_parse:
            response = self.client.post(self.URL, {"summary": "raw summary"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["work_covered"], "fractions")
        self.assertEqual(response.json()["topic_tags"], "fractions, maths")
        mock_parse.assert_called_once_with("raw summary")
        self.assertFalse(Session.objects.exists())

    def test_parse_failure_is_502(self):
        with patch("tutoring_sessions.views.zoom.parse_zoom_summary", side_effect=RuntimeError("boom")):
            response = self.client.post(self.URL, {"summary": "raw"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_blank_summary_is_rejected(self):
        with patch("tutoring_sessions.views.zoom.parse_zoom_summary") as mock_parse:
            response = self.client.post(self.URL, {"summary": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_parse.assert_not_called()
