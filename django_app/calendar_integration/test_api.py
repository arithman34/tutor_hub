"""The calendar API endpoints added for the browser app, and request validation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from students.models import Student
from tutoring_sessions.models import Session

from .models import GoogleCalendarToken

SESSIONS = "/api/v1/calendar/sessions"
ONE_OFF = "/api/v1/calendar/events"
RECURRING = "/api/v1/calendar/events/recurring"


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


def connect(user):
    return GoogleCalendarToken.objects.create(
        user=user, access_token="x", refresh_token="y", expires_at=datetime.now(timezone.utc)
    )


def google_event(event_id, summary, start):
    end = start + timedelta(hours=1)
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "htmlLink": f"https://calendar.google.com/{event_id}",
    }


class CalendarSessionsTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_conflict_when_never_connected(self):
        self.assertEqual(self.client.get(SESSIONS).status_code, status.HTTP_409_CONFLICT)

    @patch("calendar_integration.services.fetch_events")
    def test_marks_logged_events_and_matches_students(self, mock_fetch):
        connect(self.user)
        student = Student.objects.create(user=self.user, first_name="Sam", last_name="Smith")
        yesterday = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
        tomorrow = yesterday + timedelta(days=2)
        session = Session.objects.create(
            user=self.user, student=student, session_date=yesterday, session_start_time=yesterday,
            session_end_time=yesterday + timedelta(hours=1), calendar_event_id="past",
        )
        mock_fetch.return_value = [
            google_event("future", "Sam Smith - Tuition", tomorrow),
            google_event("past", "Sam Smith - Tuition", yesterday),
        ]

        response = self.client.get(SESSIONS)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.json()["items"]
        self.assertEqual([i["event_id"] for i in items], ["past", "future"])
        self.assertTrue(items[0]["logged"])
        self.assertEqual(items[0]["session_id"], str(session.id))
        self.assertFalse(items[1]["logged"])
        self.assertEqual(items[1]["student_id"], str(student.id))
        self.assertIsNone(response.json()["error"])

    @patch("calendar_integration.services.fetch_events")
    def test_filters_by_status(self, mock_fetch):
        connect(self.user)
        mock_fetch.return_value = [google_event("e1", "Lesson", datetime.now(timezone.utc) - timedelta(days=1))]
        response = self.client.get(SESSIONS, {"status": "logged"})
        self.assertEqual(response.json()["items"], [])

    @patch("calendar_integration.services.fetch_events", side_effect=RuntimeError("Google is down"))
    def test_google_failure_is_reported_not_raised(self, _mock_fetch):
        connect(self.user)
        response = self.client.get(SESSIONS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"items": [], "error": "Google is down"})

    def test_invalid_period_is_rejected(self):
        connect(self.user)
        self.assertEqual(self.client.get(SESSIONS, {"period": "decade"}).status_code, status.HTTP_400_BAD_REQUEST)

    @patch("calendar_integration.services.fetch_events", return_value=[])
    def test_only_sees_own_logged_sessions(self, _mock_fetch):
        connect(self.user)
        other = make_user("other@example.com")
        self.client.force_authenticate(other)
        connect(other)
        self.assertEqual(self.client.get(SESSIONS).json()["items"], [])

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(SESSIONS).status_code, status.HTTP_401_UNAUTHORIZED)


class OneOffEventTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.body = {"summary": "Sam Smith - Tuition", "date": "2026-12-01", "start_time": "16:00", "end_time": "17:00"}

    @patch("calendar_integration.services.create_one_off_event")
    def test_creates_event(self, mock_create):
        mock_create.return_value = google_event("new", "Sam Smith - Tuition", datetime(2026, 12, 1, 16, tzinfo=timezone.utc))
        response = self.client.post(ONE_OFF, self.body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["event_id"], "new")
        mock_create.assert_called_once_with(
            self.user, summary="Sam Smith - Tuition", date_str="2026-12-01", start_time="16:00", end_time="17:00", location=None
        )

    @patch("calendar_integration.services.create_one_off_event")
    def test_end_before_start_is_rejected(self, mock_create):
        response = self.client.post(ONE_OFF, {**self.body, "end_time": "15:00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_time", response.json())
        mock_create.assert_not_called()

    @patch("calendar_integration.services.create_one_off_event")
    def test_bad_time_format_is_rejected(self, mock_create):
        response = self.client.post(ONE_OFF, {**self.body, "start_time": "4pm"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_create.assert_not_called()

    @patch("calendar_integration.services.create_one_off_event", side_effect=ValueError("Google Calendar is not connected"))
    def test_service_error_is_a_bad_request(self, _mock_create):
        response = self.client.post(ONE_OFF, self.body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["detail"], "Google Calendar is not connected")


class RecurringEventsTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.body = {
            "summary": "Sam Smith - Tuition",
            "start_date": "2026-12-01",
            "day_configs": [{"weekday": 1, "start": "16:00", "end": "17:00"}],
        }

    @patch("calendar_integration.services.create_recurring_events", return_value=[])
    def test_creates_events_with_defaults(self, mock_create):
        response = self.client.post(RECURRING, self.body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["day_configs"], [{"weekday": 1, "start": "16:00", "end": "17:00"}])
        self.assertEqual(kwargs["start_date_str"], "2026-12-01")
        self.assertIsNone(kwargs["end_date_str"])
        self.assertEqual(kwargs["interval_weeks"], 1)

    @patch("calendar_integration.services.create_recurring_events")
    def test_rejects_invalid_requests(self, mock_create):
        invalid = [
            {**self.body, "day_configs": []},
            {**self.body, "day_configs": [{"weekday": 7, "start": "16:00", "end": "17:00"}]},
            {**self.body, "day_configs": [{"weekday": 1, "start": "17:00", "end": "16:00"}]},
            {**self.body, "end_date": "2026-11-01"},
            {**self.body, "interval_weeks": 0},
        ]
        for body in invalid:
            with self.subTest(body=body):
                self.assertEqual(self.client.post(RECURRING, body, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        mock_create.assert_not_called()


class CallbackTests(APITestCase):
    def test_stale_auth_cookie_does_not_block_googles_redirect(self):
        self.client.cookies["access_token"] = "expired-or-garbage"
        response = self.client.get("/api/v1/calendar/callback", {"error": "access_denied"})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

    def test_cookie_authenticated_user_still_identified_by_state_only(self):
        user = make_user()
        self.client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        response = self.client.get("/api/v1/calendar/callback", {"code": "x", "state": "forged"})
        self.assertIn("error=invalid_state", response.url)
