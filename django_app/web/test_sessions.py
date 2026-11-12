from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from calendar_integration.models import GoogleCalendarToken
from students.models import Student
from tutoring_sessions.models import Session

from tutoring_sessions.zoom import ParsedSession


def make_user(email, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


def connected_token(user):
    return GoogleCalendarToken.objects.create(user=user, access_token="x", refresh_token="y", expires_at=timezone.now())


def make_event(summary="Sam - Tuition", event_id="evt-1", date="2026-06-15", start="09:00", end="10:00"):
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": f"{date}T{start}:00Z"},
        "end": {"dateTime": f"{date}T{end}:00Z"},
        "htmlLink": "https://calendar.google.com/event?eid=1",
    }


class SessionsListPageTests(TestCase):
    def test_tutor_without_connection_redirects_to_connections(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/sessions")
        self.assertRedirects(response, "/connections?error=not_connected", fetch_redirect_response=False)

    def test_tutor_sees_calendar_events_merged_with_logged_state(self):
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        login(self.client, tutor)
        with patch("calendar_integration.services.fetch_events", return_value=[make_event()]):
            response = self.client.get("/sessions")
        self.assertContains(response, "Sam - Tuition")
        self.assertContains(response, "Log Session")

    def test_tutor_sees_logged_event_as_logged(self):
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        student = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        now = timezone.now()
        session = Session.objects.create(
            user=tutor,
            student=student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
            calendar_event_id="evt-1",
        )
        login(self.client, tutor)
        with patch("calendar_integration.services.fetch_events", return_value=[make_event(event_id="evt-1")]):
            response = self.client.get("/sessions")
        self.assertContains(response, "Logged")
        self.assertContains(response, f"/sessions/{session.id}")

    def test_fetch_failure_shows_error_banner(self):
        tutor = make_user("tutor@example.com")
        connected_token(tutor)
        login(self.client, tutor)
        with patch("calendar_integration.services.fetch_events", side_effect=RuntimeError("boom")):
            response = self.client.get("/sessions")
        self.assertContains(response, "boom")

    def test_another_accounts_logged_event_is_not_shown_as_logged(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        connected_token(tutor)
        other_student = Student.objects.create(user=other, first_name="Pat", last_name="Jones")
        now = timezone.now()
        other_session = Session.objects.create(
            user=other,
            student=other_student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
            calendar_event_id="evt-1",
        )
        login(self.client, tutor)
        with patch("calendar_integration.services.fetch_events", return_value=[make_event(event_id="evt-1")]):
            response = self.client.get("/sessions")
        self.assertNotContains(response, f"/sessions/{other_session.id}")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/sessions")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)


class SessionsNewPageTests(TestCase):
    def test_tutor_sees_own_active_students_only(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        Student.objects.create(user=tutor, first_name="Old", last_name="Student", is_active=False)
        Student.objects.create(user=make_user("other@example.com"), first_name="Pat", last_name="Jones", is_active=True)
        login(self.client, tutor)
        response = self.client.get("/sessions/new")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Old Student")
        self.assertNotContains(response, "Pat Jones")


class SessionCreateTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith")

    def _payload(self, **overrides):
        payload = {
            "student_id": str(self.student.id),
            "session_date": "2026-06-15",
            "start_time": "09:00",
            "end_time": "10:00",
            "work_covered": "fractions",
        }
        payload.update(overrides)
        return payload

    def test_tutor_can_create_session(self):
        login(self.client, self.tutor)
        response = self.client.post("/sessions", self._payload())
        self.assertRedirects(response, "/sessions", fetch_redirect_response=False)
        session = Session.objects.get()
        self.assertEqual(session.user, self.tutor)
        self.assertEqual(session.work_covered, "fractions")

    def test_cannot_log_session_for_another_accounts_student(self):
        login(self.client, make_user("other@example.com"))
        response = self.client.post("/sessions", self._payload())
        self.assertRedirects(response, "/sessions/new", fetch_redirect_response=False)
        self.assertEqual(Session.objects.count(), 0)

    def test_no_show_session_created(self):
        login(self.client, self.tutor)
        self.client.post("/sessions", self._payload(is_no_show="on", work_covered=""))
        session = Session.objects.get()
        self.assertTrue(session.is_no_show)


class ZoomParseTests(TestCase):
    def test_tutor_gets_parsed_fields(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        with patch("web.sessions_views.ai.parse_zoom_summary") as mock_parse:
            mock_parse.return_value = ParsedSession(
                work_covered="covered fractions",
                student_actions="practice worksheet",
                tutor_actions="prep next worksheet",
                next_lesson_focus="decimals",
                topic_tags="fractions, maths",
            )
            response = self.client.post("/sessions/zoom-parse", {"zoom_summary": "raw summary text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["work_covered"], "covered fractions")

    def test_parse_failure_returns_502(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        with patch("web.sessions_views.ai.parse_zoom_summary", side_effect=RuntimeError("boom")):
            response = self.client.post("/sessions/zoom-parse", {"zoom_summary": "x"})
        self.assertEqual(response.status_code, 502)


class SessionDetailAndMutationTests(TestCase):
    def setUp(self):
        self.tutor = make_user("tutor@example.com")
        self.other_tutor = make_user("other@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", is_active=True)
        now = timezone.now()
        self.session = Session.objects.create(
            user=self.tutor,
            student=self.student,
            session_date=now,
            session_start_time=now,
            session_end_time=now + timedelta(hours=1),
            work_covered="fractions",
        )

    def test_owner_can_view(self):
        login(self.client, self.tutor)
        response = self.client.get(f"/sessions/{self.session.id}")
        self.assertContains(response, "fractions")

    def test_other_tutor_redirected(self):
        login(self.client, self.other_tutor)
        response = self.client.get(f"/sessions/{self.session.id}")
        self.assertRedirects(response, "/sessions", fetch_redirect_response=False)

    def test_update_details_does_not_wipe_notes(self):
        """Regression: the Details form has no notes fields, so submitting it
        must not blank out work_covered/etc — see the comment in
        web/sessions_views.py:session_update."""
        login(self.client, self.tutor)
        self.client.post(
            f"/sessions/{self.session.id}/update",
            {
                "student_id": str(self.student.id),
                "session_date": "2026-07-01",
                "start_time": "10:00",
                "end_time": "11:00",
            },
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.work_covered, "fractions")
        self.assertEqual(self.session.session_date.strftime("%Y-%m-%d"), "2026-07-01")

    def test_update_notes_form_updates_notes(self):
        login(self.client, self.tutor)
        self.client.post(
            f"/sessions/{self.session.id}/update",
            {
                "student_id": str(self.student.id),
                "session_date": self.session.session_date.strftime("%Y-%m-%d"),
                "start_time": self.session.session_start_time.strftime("%H:%M"),
                "end_time": self.session.session_end_time.strftime("%H:%M"),
                "work_covered": "decimals now",
            },
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.work_covered, "decimals now")

    def test_owner_can_delete(self):
        login(self.client, self.tutor)
        response = self.client.post(f"/sessions/{self.session.id}/delete")
        self.assertRedirects(response, "/sessions", fetch_redirect_response=False)
        self.assertFalse(Session.objects.filter(id=self.session.id).exists())

    def test_other_tutor_cannot_delete(self):
        login(self.client, self.other_tutor)
        self.client.post(f"/sessions/{self.session.id}/delete")
        self.assertTrue(Session.objects.filter(id=self.session.id).exists())

    def test_other_tutor_cannot_update(self):
        login(self.client, self.other_tutor)
        self.client.post(f"/sessions/{self.session.id}/update", {"work_covered": "hacked"})
        self.session.refresh_from_db()
        self.assertEqual(self.session.work_covered, "fractions")

    def test_cannot_move_session_to_another_accounts_student(self):
        foreign = Student.objects.create(user=self.other_tutor, first_name="Pat", last_name="Jones")
        login(self.client, self.tutor)
        self.client.post(f"/sessions/{self.session.id}/update", {"student_id": str(foreign.id)})
        self.session.refresh_from_db()
        self.assertEqual(self.session.student, self.student)


class SessionFormsCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = make_user("tutor@example.com")
        self.student = Student.objects.create(user=self.tutor, first_name="Sam", last_name="Smith", is_active=True)
        now = timezone.now()
        self.session = Session.objects.create(
            user=self.tutor, student=self.student, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=1)
        )
        login(self.client, self.tutor)

    def _csrf_token(self, get_path):
        self.client.get(get_path)
        return self.client.cookies["csrftoken"].value

    def test_create_form_includes_working_csrf_token(self):
        token = self._csrf_token("/sessions/new")
        response = self.client.post(
            "/sessions",
            {
                "student_id": str(self.student.id),
                "session_date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "10:00",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_update_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/sessions/{self.session.id}")
        response = self.client.post(
            f"/sessions/{self.session.id}/update",
            {
                "student_id": str(self.student.id),
                "session_date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "10:00",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_form_includes_working_csrf_token(self):
        token = self._csrf_token(f"/sessions/{self.session.id}")
        response = self.client.post(f"/sessions/{self.session.id}/delete", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
