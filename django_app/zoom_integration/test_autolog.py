import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from calendar_integration.models import GoogleCalendarToken
from students.models import Student
from tutoring_sessions.models import Session
from tutoring_sessions.zoom import ParsedSession

from . import autolog, services, webhook
from .models import ZoomMeetingEvent, ZoomToken

SECRET = "webhook-secret"
UTC = timezone.utc

# A 16:00 lesson in British Summer Time: 15:00 real UTC, stored by TutorHub as 16:00 "UTC".
SUMMER_REAL = datetime(2026, 7, 14, 15, 0, tzinfo=UTC)
SUMMER_WALL = datetime(2026, 7, 14, 16, 0, tzinfo=UTC)
# A winter lesson, where wall-clock and UTC agree.
WINTER = datetime(2026, 11, 12, 16, 0, tzinfo=UTC)

NOTES = ParsedSession(work_covered="Fractions", student_actions="- worksheet", tutor_actions="", next_lesson_focus="Decimals", topic_tags="maths")


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_user(email="tutor@example.com"):
    return User.objects.create_user(email=email, password="x", first_name="A", last_name="B")


def connect_zoom(user):
    return ZoomToken.objects.create(user=user, access_token="at", refresh_token="rt", expires_at=datetime.now(UTC) + timedelta(hours=1))


def connect_google(user):
    return GoogleCalendarToken.objects.create(user=user, access_token="g", refresh_token="gr", expires_at=datetime.now(UTC) + timedelta(hours=1))


def meeting(start: datetime, minutes=55, participants=2):
    return {"start_time": iso(start), "end_time": iso(start + timedelta(minutes=minutes)), "participants_count": participants}


def calendar_event(event_id, title, wall_start: datetime, offset="+01:00", minutes=60):
    # Google sends local times with an offset; parse_event keeps the local part.
    end = wall_start + timedelta(minutes=minutes)
    return {
        "id": event_id,
        "summary": title,
        "recurringEventId": "rec1",
        "htmlLink": f"https://calendar.google.com/{event_id}",
        "start": {"dateTime": wall_start.strftime("%Y-%m-%dT%H:%M:00") + offset},
        "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:00") + offset},
    }


def sign(body: bytes, timestamp: str | None = None, secret=SECRET):
    timestamp = timestamp or str(int(time.time()))
    digest = hmac.new(secret.encode(), f"v0:{timestamp}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return {"HTTP_X_ZM_REQUEST_TIMESTAMP": timestamp, "HTTP_X_ZM_SIGNATURE": f"v0={digest}"}


class WallClockTests(APITestCase):
    def test_summer_time_is_shifted_to_local(self):
        self.assertEqual(services.to_wall_clock(SUMMER_REAL), SUMMER_WALL)

    def test_winter_time_is_unchanged(self):
        self.assertEqual(services.to_wall_clock(WINTER), WINTER)

    def test_matching_a_summer_session(self):
        # The Zoom instance starts at 15:02 real UTC; the session is stored as 16:00.
        instances = [{"uuid": "u", "start_time": iso(SUMMER_REAL + timedelta(minutes=2))}]
        self.assertEqual(services.closest_instance(instances, SUMMER_WALL)["uuid"], "u")

    def test_summer_match_ignores_a_lesson_an_hour_out(self):
        # Without the conversion, a 16:00 real-UTC meeting (17:00 local) would look like a 16:00 lesson.
        instances = [{"uuid": "wrong", "start_time": iso(SUMMER_WALL + timedelta(minutes=61))}]
        self.assertIsNone(services.closest_instance(instances, SUMMER_WALL))


@override_settings(ZOOM_WEBHOOK_SECRET_TOKEN=SECRET)
class SignatureTests(APITestCase):
    def test_valid(self):
        headers = sign(b'{"a":1}')
        self.assertTrue(webhook.is_valid_signature(b'{"a":1}', headers["HTTP_X_ZM_REQUEST_TIMESTAMP"], headers["HTTP_X_ZM_SIGNATURE"]))

    def test_tampered_body(self):
        headers = sign(b'{"a":1}')
        self.assertFalse(webhook.is_valid_signature(b'{"a":2}', headers["HTTP_X_ZM_REQUEST_TIMESTAMP"], headers["HTTP_X_ZM_SIGNATURE"]))

    def test_wrong_secret(self):
        headers = sign(b"{}", secret="other")
        self.assertFalse(webhook.is_valid_signature(b"{}", headers["HTTP_X_ZM_REQUEST_TIMESTAMP"], headers["HTTP_X_ZM_SIGNATURE"]))

    def test_stale_timestamp(self):
        old = str(int(time.time()) - 600)
        headers = sign(b"{}", timestamp=old)
        self.assertFalse(webhook.is_valid_signature(b"{}", old, headers["HTTP_X_ZM_SIGNATURE"]))

    def test_millisecond_timestamp(self):
        ms = str(int(time.time() * 1000))
        headers = sign(b"{}", timestamp=ms)
        self.assertTrue(webhook.is_valid_signature(b"{}", ms, headers["HTTP_X_ZM_SIGNATURE"]))

    def test_missing_headers(self):
        self.assertFalse(webhook.is_valid_signature(b"{}", None, None))

    @override_settings(ZOOM_WEBHOOK_SECRET_TOKEN="")
    def test_no_secret_configured_refuses_everything(self):
        headers = sign(b"{}", secret="")
        self.assertFalse(webhook.is_valid_signature(b"{}", headers["HTTP_X_ZM_REQUEST_TIMESTAMP"], headers["HTTP_X_ZM_SIGNATURE"]))


@override_settings(ZOOM_WEBHOOK_SECRET_TOKEN=SECRET, ZOOM_PROCESS_INLINE=True)
class WebhookViewTests(APITestCase):
    URL = "/api/v1/zoom/webhook"

    def setUp(self):
        self.user = make_user()
        connect_zoom(self.user)
        self.student = Student.objects.create(user=self.user, first_name="Sam", last_name="Smith", zoom_meeting_id="123 4567 8901")

    def post(self, payload, signed=True):
        body = json.dumps(payload).encode()
        headers = sign(body) if signed else {}
        return self.client.post(self.URL, data=body, content_type="application/json", **headers)

    def summary_payload(self, uuid="uuid-1", meeting_id=12345678901):
        return {
            "event": "meeting.summary_completed",
            "payload": {"object": {"meeting_id": meeting_id, "meeting_uuid": uuid, "meeting_start_time": iso(WINTER)}},
        }

    def test_unsigned_request_is_refused(self):
        resp = self.post({"event": "endpoint.url_validation", "payload": {"plainToken": "abc"}}, signed=False)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_url_validation(self):
        resp = self.post({"event": "endpoint.url_validation", "payload": {"plainToken": "abc"}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected = hmac.new(SECRET.encode(), b"abc", hashlib.sha256).hexdigest()
        self.assertEqual(resp.json(), {"plainToken": "abc", "encryptedToken": expected})

    def test_other_events_are_acknowledged_and_ignored(self):
        resp = self.post({"event": "meeting.started", "payload": {"object": {}}})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ZoomMeetingEvent.objects.exists())

    @patch("zoom_integration.autolog.parse_zoom_summary", return_value=NOTES)
    @patch("zoom_integration.services.fetch_summary", return_value="We did fractions.")
    @patch("zoom_integration.services.past_meeting", return_value=meeting(WINTER))
    def test_summary_event_logs_the_lesson(self, *_):
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.post(self.summary_payload())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        event = ZoomMeetingEvent.objects.get()
        self.assertEqual(event.status, ZoomMeetingEvent.Status.DONE)
        self.assertEqual(event.source, ZoomMeetingEvent.Source.WEBHOOK)
        session = Session.objects.get()
        self.assertEqual(event.session, session)
        self.assertEqual(session.student, self.student)
        self.assertEqual(session.work_covered, "Fractions")
        self.assertIsNone(session.tutor_actions)
        self.assertEqual(session.zoom_summary_raw, "We did fractions.")

    @patch("zoom_integration.autolog.process_event")
    def test_repeated_delivery_is_processed_once(self, mock_process):
        mock_process.side_effect = lambda event_id: ZoomMeetingEvent.objects.filter(id=event_id).update(status="done")
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                self.post(self.summary_payload())
        self.assertEqual(ZoomMeetingEvent.objects.count(), 1)
        self.assertEqual(mock_process.call_count, 1)

    def test_unknown_meeting_is_ignored(self):
        resp = self.post(self.summary_payload(meeting_id=999))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ZoomMeetingEvent.objects.exists())

    def test_meeting_on_a_tutor_without_zoom_is_ignored(self):
        ZoomToken.objects.all().delete()
        self.post(self.summary_payload())
        self.assertFalse(ZoomMeetingEvent.objects.exists())

    def test_meeting_id_on_two_students_is_ignored(self):
        Student.objects.create(user=self.user, first_name="Alex", last_name="Jones", zoom_meeting_id="12345678901")
        self.post(self.summary_payload())
        self.assertFalse(ZoomMeetingEvent.objects.exists())


@patch("zoom_integration.autolog.parse_zoom_summary", return_value=NOTES)
@patch("zoom_integration.services.fetch_summary", return_value="We did fractions.")
@patch("zoom_integration.services.past_meeting")
class ProcessEventTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        connect_zoom(self.user)
        self.student = Student.objects.create(user=self.user, first_name="Sam", last_name="Smith", zoom_meeting_id="12345678901")

    def event(self, start=WINTER, uuid="uuid-1"):
        return ZoomMeetingEvent.objects.create(
            user=self.user, student=self.student, meeting_id="12345678901", meeting_uuid=uuid, start_time=start, source="webhook"
        )

    def test_uses_the_calendar_events_times_and_links_it(self, mock_meeting, *_):
        connect_google(self.user)
        # Joined 3 minutes late and overran by 20: billing should follow the booking.
        mock_meeting.return_value = meeting(SUMMER_REAL + timedelta(minutes=3), minutes=77)
        booked = calendar_event("evt1", "Sam - Tuition", SUMMER_WALL)
        with patch("calendar_integration.services.fetch_events", return_value=[booked]):
            self.assertEqual(autolog.process_event(self.event(SUMMER_REAL).id), "logged")

        session = Session.objects.get()
        self.assertEqual(session.session_start_time, SUMMER_WALL)
        self.assertEqual(session.session_end_time, SUMMER_WALL + timedelta(hours=1))
        self.assertEqual(session.session_date, SUMMER_WALL)
        self.assertEqual((session.calendar_event_id, session.calendar_recurring_id), ("evt1", "rec1"))
        self.assertEqual(session.calendar_html_link, "https://calendar.google.com/evt1")
        self.assertFalse(session.is_no_show)

    def test_ignores_another_students_calendar_event(self, mock_meeting, *_):
        connect_google(self.user)
        mock_meeting.return_value = meeting(WINTER)
        other = calendar_event("evt2", "Alex - Tuition", WINTER, offset="+00:00")
        with patch("calendar_integration.services.fetch_events", return_value=[other]):
            autolog.process_event(self.event().id)
        self.assertIsNone(Session.objects.get().calendar_event_id)

    def test_falls_back_to_zoom_times_as_wall_clock(self, mock_meeting, *_):
        mock_meeting.return_value = meeting(SUMMER_REAL, minutes=50)
        autolog.process_event(self.event(SUMMER_REAL).id)
        session = Session.objects.get()
        self.assertEqual(session.session_start_time, SUMMER_WALL)
        self.assertEqual(session.session_end_time, SUMMER_WALL + timedelta(minutes=50))

    def test_calendar_outage_falls_back_to_zoom_times(self, mock_meeting, *_):
        connect_google(self.user)
        mock_meeting.return_value = meeting(WINTER)
        with patch("calendar_integration.services.fetch_events", side_effect=RuntimeError("Google down")):
            self.assertEqual(autolog.process_event(self.event().id), "logged")
        self.assertEqual(Session.objects.get().session_start_time, WINTER)

    def test_no_show_is_logged_without_notes(self, mock_meeting, mock_summary, mock_parse):
        mock_meeting.return_value = meeting(WINTER, minutes=12, participants=1)
        autolog.process_event(self.event().id)

        session = Session.objects.get()
        self.assertTrue(session.is_no_show)
        self.assertIsNone(session.work_covered)
        mock_summary.assert_not_called()
        mock_parse.assert_not_called()

    def test_fills_an_already_logged_session_with_empty_notes(self, mock_meeting, *_):
        mock_meeting.return_value = meeting(WINTER + timedelta(minutes=4))
        existing = Session.objects.create(
            user=self.user, student=self.student, session_date=WINTER, session_start_time=WINTER, session_end_time=WINTER + timedelta(hours=1)
        )
        self.assertEqual(autolog.process_event(self.event().id), "updated")
        existing.refresh_from_db()
        self.assertEqual(existing.work_covered, "Fractions")
        self.assertEqual(existing.zoom_meeting_uuid, "uuid-1")
        self.assertEqual(Session.objects.count(), 1)

    def test_never_overwrites_notes_the_tutor_wrote(self, mock_meeting, _summary, mock_parse):
        mock_meeting.return_value = meeting(WINTER)
        existing = Session.objects.create(
            user=self.user,
            student=self.student,
            session_date=WINTER,
            session_start_time=WINTER,
            session_end_time=WINTER + timedelta(hours=1),
            work_covered="My own notes",
        )
        autolog.process_event(self.event().id)
        existing.refresh_from_db()
        self.assertEqual(existing.work_covered, "My own notes")
        self.assertEqual(existing.zoom_summary_raw, "We did fractions.")
        mock_parse.assert_not_called()

    def test_never_changes_a_tutors_no_show(self, mock_meeting, *_):
        mock_meeting.return_value = meeting(WINTER)
        existing = Session.objects.create(
            user=self.user, student=self.student, session_date=WINTER, session_start_time=WINTER, session_end_time=WINTER, is_no_show=True
        )
        autolog.process_event(self.event().id)
        existing.refresh_from_db()
        self.assertTrue(existing.is_no_show)
        self.assertIsNone(existing.work_covered)

    def test_matches_an_existing_session_by_its_calendar_event(self, mock_meeting, *_):
        connect_google(self.user)
        mock_meeting.return_value = meeting(WINTER)
        # Logged by hand at a corrected time, but linked to the same booking.
        existing = Session.objects.create(
            user=self.user,
            student=self.student,
            session_date=WINTER,
            session_start_time=WINTER + timedelta(hours=3),
            session_end_time=WINTER + timedelta(hours=4),
            calendar_event_id="evt1",
        )
        with patch("calendar_integration.services.fetch_events", return_value=[calendar_event("evt1", "Sam - Tuition", WINTER, offset="+00:00")]):
            self.assertEqual(autolog.process_event(self.event().id), "updated")
        self.assertEqual(Session.objects.get(), existing)

    def test_a_session_for_another_student_is_not_matched(self, mock_meeting, *_):
        mock_meeting.return_value = meeting(WINTER)
        alex = Student.objects.create(user=self.user, first_name="Alex", last_name="Jones")
        Session.objects.create(user=self.user, student=alex, session_date=WINTER, session_start_time=WINTER, session_end_time=WINTER)
        self.assertEqual(autolog.process_event(self.event().id), "logged")
        self.assertEqual(Session.objects.filter(student=self.student).count(), 1)

    def test_waits_for_a_summary_that_isnt_ready(self, mock_meeting, mock_summary, _parse):
        just_now = datetime.now(UTC) - timedelta(minutes=70)
        mock_meeting.return_value = meeting(just_now)
        mock_summary.side_effect = services.NotFoundError("not yet")
        event = self.event(just_now)
        self.assertEqual(autolog.process_event(event.id), "waiting")
        event.refresh_from_db()
        self.assertEqual((event.status, event.attempts), ("pending", 1))
        self.assertFalse(Session.objects.exists())

    def test_logs_without_notes_once_the_summary_isnt_coming(self, mock_meeting, mock_summary, _parse):
        mock_meeting.return_value = meeting(WINTER)
        mock_summary.side_effect = services.NotFoundError("summaries off")
        self.assertEqual(autolog.process_event(self.event().id), "logged")
        session = Session.objects.get()
        self.assertFalse(session.is_no_show)
        self.assertIsNone(session.work_covered)

    def test_meeting_zoom_hasnt_finished_waits(self, mock_meeting, *_):
        mock_meeting.side_effect = services.NotFoundError("still going")
        self.assertEqual(autolog.process_event(self.event().id), "waiting")

    def test_parse_failure_saves_nothing_and_retries(self, mock_meeting, _summary, mock_parse):
        mock_meeting.return_value = meeting(WINTER)
        mock_parse.side_effect = RuntimeError("OpenAI down")
        event = self.event()
        self.assertEqual(autolog.process_event(event.id), "waiting")
        self.assertFalse(Session.objects.exists())
        event.refresh_from_db()
        self.assertIn("OpenAI down", event.last_error)

    def test_gives_up_after_repeated_failures(self, mock_meeting, *_):
        mock_meeting.side_effect = services.ZoomAPIError("Zoom returned an error (500)")
        event = self.event()
        event.attempts = autolog.MAX_ATTEMPTS - 1
        event.save()
        self.assertEqual(autolog.process_event(event.id), "failed")
        event.refresh_from_db()
        self.assertEqual(event.status, "failed")

    def test_a_finished_event_is_not_processed_again(self, mock_meeting, *_):
        mock_meeting.return_value = meeting(WINTER)
        event = self.event()
        autolog.process_event(event.id)
        self.assertIsNone(autolog.process_event(event.id))
        self.assertEqual(Session.objects.count(), 1)


@patch("zoom_integration.autolog.parse_zoom_summary", return_value=NOTES)
@patch("zoom_integration.services.fetch_summary", return_value="Summary.")
@patch("zoom_integration.services.past_meeting")
@patch("zoom_integration.services.list_past_instances")
class SweepTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        connect_zoom(self.user)
        self.client.force_authenticate(self.user)
        self.student = Student.objects.create(user=self.user, first_name="Sam", last_name="Smith", zoom_meeting_id="123 4567 8901")
        self.recent = (datetime.now(UTC) - timedelta(days=2)).replace(microsecond=0)

    def test_logs_recent_lessons_and_skips_old_ones(self, mock_instances, mock_meeting, *_):
        mock_instances.return_value = [
            {"uuid": "recent", "start_time": iso(self.recent)},
            {"uuid": "old", "start_time": iso(self.recent - timedelta(days=30))},
        ]
        mock_meeting.return_value = meeting(self.recent, participants=1)

        resp = self.client.post("/api/v1/zoom/sweep")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json(), {"logged": 1, "updated": 0, "waiting": 0, "failed": 0})
        mock_instances.assert_called_once_with(self.user, "12345678901")
        event = ZoomMeetingEvent.objects.get()
        self.assertEqual((event.meeting_uuid, event.source), ("recent", "sweep"))
        self.assertTrue(Session.objects.get().is_no_show)

    def test_running_twice_logs_nothing_new(self, mock_instances, mock_meeting, *_):
        mock_instances.return_value = [{"uuid": "recent", "start_time": iso(self.recent)}]
        mock_meeting.return_value = meeting(self.recent)
        self.client.post("/api/v1/zoom/sweep")
        resp = self.client.post("/api/v1/zoom/sweep")
        self.assertEqual(resp.json(), {"logged": 0, "updated": 0, "waiting": 0, "failed": 0})
        self.assertEqual(Session.objects.count(), 1)

    def test_skips_a_meeting_id_zoom_doesnt_know(self, mock_instances, *_):
        mock_instances.side_effect = services.NotFoundError("no such meeting")
        self.assertEqual(self.client.post("/api/v1/zoom/sweep").status_code, status.HTTP_200_OK)

    def test_not_connected(self, *_):
        ZoomToken.objects.all().delete()
        self.assertEqual(self.client.post("/api/v1/zoom/sweep").status_code, status.HTTP_409_CONFLICT)

    def test_zoom_error(self, mock_instances, *_):
        mock_instances.side_effect = services.ZoomAPIError("Zoom returned an error (500)")
        self.assertEqual(self.client.post("/api/v1/zoom/sweep").status_code, status.HTTP_502_BAD_GATEWAY)

    def test_demo_cannot_sweep(self, *_):
        demo = User.objects.create_user(email="demo@example.com", password="x", first_name="D", last_name="D", is_demo=True)
        self.client.force_authenticate(demo)
        self.assertEqual(self.client.post("/api/v1/zoom/sweep").status_code, status.HTTP_403_FORBIDDEN)

    def test_management_command_sweeps_every_connected_tutor(self, mock_instances, mock_meeting, *_):
        mock_instances.return_value = [{"uuid": "recent", "start_time": iso(self.recent)}]
        mock_meeting.return_value = meeting(self.recent)
        out = StringIO()
        call_command("zoom_catch_up", stdout=out)
        self.assertIn("'logged': 1", out.getvalue())
        self.assertEqual(Session.objects.count(), 1)
