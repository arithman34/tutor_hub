from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole
from students.models import Student
from tutoring_sessions.models import Session

from .ai import ParsedSession


def make_user(email, role=UserRole.TUTOR, **extra):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B", role=role, **extra)


def login(client, user):
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class SessionsListPageTests(TestCase):
    def test_tutor_sees_only_own_sessions(self):
        tutor = make_user("tutor@example.com")
        other = make_user("other@example.com")
        s1 = Student.objects.create(user=tutor, first_name="Sam", last_name="Smith")
        s2 = Student.objects.create(user=other, first_name="Pat", last_name="Jones")
        now = timezone.now()
        Session.objects.create(user=tutor, student=s1, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=1))
        Session.objects.create(user=other, student=s2, session_date=now, session_start_time=now, session_end_time=now + timedelta(hours=1))

        login(self.client, tutor)
        response = self.client.get("/sessions")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Pat")

    def test_tutor_sees_log_session_link(self):
        tutor = make_user("tutor@example.com")
        login(self.client, tutor)
        response = self.client.get("/sessions")
        self.assertContains(response, "Log Session")

    def test_admin_does_not_see_log_session_link(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/sessions")
        self.assertNotContains(response, "Log Session")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/sessions")
        self.assertRedirects(response, "/login", fetch_redirect_response=False)


class SessionsNewPageTests(TestCase):
    def test_admin_redirected_away(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.get("/sessions/new")
        self.assertRedirects(response, "/sessions", fetch_redirect_response=False)

    def test_tutor_sees_own_active_students_only(self):
        tutor = make_user("tutor@example.com")
        Student.objects.create(user=tutor, first_name="Sam", last_name="Smith", is_active=True)
        Student.objects.create(user=tutor, first_name="Old", last_name="Student", is_active=False)
        login(self.client, tutor)
        response = self.client.get("/sessions/new")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "Old Student")


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

    def test_admin_cannot_create_session(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        self.client.post("/sessions", self._payload(student_id=str(self.student.id)))
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

    def test_admin_forbidden(self):
        admin = make_user("admin@example.com", UserRole.ADMIN)
        login(self.client, admin)
        response = self.client.post("/sessions/zoom-parse", {"zoom_summary": "x"})
        self.assertEqual(response.status_code, 403)

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
