from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from calendar_integration.models import GoogleCalendarToken
from students.models import Student


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


def connected_token(user):
    return GoogleCalendarToken.objects.create(user=user, access_token="x", refresh_token="y", expires_at=timezone.now())


class CalendarCreatePageTests(TestCase):
    def test_redirects_when_not_connected(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/calendar/create")
        self.assertRedirects(response, "/connections?error=not_connected", fetch_redirect_response=False)

    def test_shows_form_when_connected(self):
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        login(self.client, tutor)
        response = self.client.get("/calendar/create")
        self.assertContains(response, "Sam")

    def test_only_active_students_shown(self):
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        Student.objects.create(user=tutor, first_name="Old", last_name="One", is_active=False)
        login(self.client, tutor)
        response = self.client.get("/calendar/create")
        self.assertNotContains(response, "Old One")


class CalendarCreateTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        connected_token(self.tutor)
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", is_active=True)
        login(self.client, self.tutor)

    def test_no_student_redirects_with_error(self):
        response = self.client.post("/calendar/create", {"session_type": "oneoff"})
        self.assertRedirects(response, "/calendar/create?error=no_student", fetch_redirect_response=False)

    @patch("calendar_integration.services.create_one_off_event")
    def test_oneoff_creates_event_and_redirects(self, mock_create):
        response = self.client.post(
            "/calendar/create",
            {
                "session_type": "oneoff",
                "student_id": str(self.student.id),
                "date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        self.assertRedirects(response, "/sessions?created=1", fetch_redirect_response=False)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["summary"], "Sam - Tuition")

    def test_recurring_without_days_redirects_with_error(self):
        response = self.client.post(
            "/calendar/create",
            {"session_type": "recurring", "student_id": str(self.student.id), "start_date": "2026-06-15"},
        )
        self.assertRedirects(response, "/calendar/create?error=no_days", fetch_redirect_response=False)

    @patch("calendar_integration.services.create_recurring_events")
    def test_recurring_creates_events_and_redirects(self, mock_create):
        mock_create.return_value = [{}]
        response = self.client.post(
            "/calendar/create",
            {
                "session_type": "recurring",
                "student_id": str(self.student.id),
                "start_date": "2026-06-15",
                "day_0_enabled": "1",
                "day_0_start": "09:00",
                "day_0_end": "10:00",
            },
        )
        self.assertRedirects(response, "/sessions?created=1", fetch_redirect_response=False)
        mock_create.assert_called_once()

    @patch("calendar_integration.services.create_one_off_event", side_effect=RuntimeError("boom"))
    def test_creation_failure_redirects_with_error_detail(self, mock_create):
        response = self.client.post(
            "/calendar/create",
            {
                "session_type": "oneoff",
                "student_id": str(self.student.id),
                "date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        self.assertRedirects(response, "/calendar/create?error=boom", fetch_redirect_response=False)


class CalendarPageRedirectTests(TestCase):
    def test_calendar_redirects_to_sessions(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/calendar")
        self.assertRedirects(response, "/sessions", fetch_redirect_response=False)


class CalendarCreateFormCsrfTests(TestCase):
    def test_create_form_includes_working_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        login(client, tutor)
        client.get("/calendar/create")
        token = client.cookies["csrftoken"].value
        with patch("calendar_integration.services.create_one_off_event"):
            response = client.post(
                "/calendar/create",
                {
                    "session_type": "oneoff",
                    "student_id": str(student.id),
                    "date": "2026-06-15",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "csrfmiddlewaretoken": token,
                },
            )
        self.assertEqual(response.status_code, 302)
