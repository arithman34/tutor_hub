"""Turning finished Zoom lessons into logged Sessions, with no clicks.

A ZoomMeetingEvent (from the summary webhook or the catch-up sweep) is
processed into a Session:

- Attendance comes from the meeting's participant count. Only the host there
  means a no-show, which is logged (and billed, like a hand-logged no-show)
  with no notes.
- Times come from the matching Google Calendar event, so the payee is billed
  for the booked lesson rather than however long the call ran. Zoom's own
  times are the fallback.
- A session that's already logged is only filled in: empty notes get the
  summary's, and nothing the tutor wrote or set is overwritten.
"""

import logging
import threading
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import close_old_connections, transaction

from calendar_integration import services as calendar
from calendar_integration.models import GoogleCalendarToken
from tutoring_sessions.models import Session
from tutoring_sessions.zoom import parse_zoom_summary

from . import services
from .models import ZoomMeetingEvent, ZoomToken

logger = logging.getLogger(__name__)

# A summary normally lands within minutes of the meeting ending. Until this long
# after, a missing one is "not ready yet" rather than "never coming".
SUMMARY_WAIT = timedelta(hours=2)
MAX_ATTEMPTS = 8
SWEEP_DAYS = 7

NOTE_FIELDS = ("work_covered", "student_actions", "tutor_actions", "next_lesson_focus", "topic_tags")


class NotReady(Exception):
    """Zoom hasn't finished with the meeting yet. Try again later."""


# --- Dispatch ---------------------------------------------------------------


def dispatch(event_id) -> None:
    """Process an event after the current transaction commits, in a background
    thread so the webhook can answer Zoom within its 3 seconds. If the server
    stops first, the event stays pending for the catch-up sweep."""
    if settings.ZOOM_PROCESS_INLINE:
        transaction.on_commit(lambda: process_event(event_id))
    else:
        transaction.on_commit(lambda: threading.Thread(target=_process_in_thread, args=(event_id,), daemon=True).start())


def _process_in_thread(event_id) -> None:
    try:
        process_event(event_id)
    except Exception:
        logger.exception("Processing Zoom meeting event %s failed", event_id)
    finally:
        close_old_connections()


# --- Processing -------------------------------------------------------------


def process_event(event_id) -> str | None:
    """Log one pending event as a Session. Returns its Outcome ("logged",
    "no_show", "notes_filled" or "linked"), "waiting" or "failed", or None if it
    wasn't pending (or another worker has it)."""
    with transaction.atomic():
        event = (
            ZoomMeetingEvent.objects.select_for_update(skip_locked=True)
            .select_related("user", "student")
            .filter(id=event_id, status=ZoomMeetingEvent.Status.PENDING)
            .first()
        )
        if not event:
            return None
        try:
            with transaction.atomic():
                outcome = _log(event)
        except NotReady as exc:
            outcome = _retry_later(event, str(exc))
        except Exception as exc:
            logger.exception("Logging Zoom meeting %s failed", event.meeting_uuid)
            outcome = _retry_later(event, str(exc) or exc.__class__.__name__)
        event.save()
        return outcome


def _retry_later(event: ZoomMeetingEvent, error: str) -> str:
    event.attempts += 1
    event.last_error = error[:1000]
    if event.attempts >= MAX_ATTEMPTS:
        event.status = ZoomMeetingEvent.Status.FAILED
        return "failed"
    return "waiting"


def _log(event: ZoomMeetingEvent) -> str:
    user, student = event.user, event.student

    try:
        details = services.past_meeting(user, event.meeting_uuid)
    except services.NotFoundError as exc:
        raise NotReady(str(exc)) from exc

    real_start = services.parse_zoom_time(details["start_time"]) if details.get("start_time") else event.start_time
    if real_start is None:
        raise NotReady("Zoom hasn't reported when the meeting started.")
    if details.get("end_time"):
        real_end = services.parse_zoom_time(details["end_time"])
    else:
        real_end = real_start + timedelta(minutes=details.get("duration") or 60)
    event.start_time = real_start

    participants = details.get("participants_count")
    no_show = participants is not None and participants <= 1

    summary = None
    if not no_show:
        try:
            summary = services.fetch_summary(user, event.meeting_uuid)
        except services.NotFoundError as exc:
            if datetime.now(timezone.utc) - real_end < SUMMARY_WAIT:
                raise NotReady(str(exc)) from exc
            # Long enough that it isn't coming (summaries off for that meeting).
            # The lesson still happened, so log it without notes.

    wall_start, wall_end = services.to_wall_clock(real_start), services.to_wall_clock(real_end)
    booked = find_calendar_event(user, student, real_start, wall_start)
    session = find_session(user, student, booked, booked["start"] if booked else wall_start)

    notes = None
    if summary and not no_show and (session is None or (not session.is_no_show and not has_notes(session))):
        notes = {field: (value or None) for field, value in asdict(parse_zoom_summary(summary)).items()}

    if session:
        if notes:
            for field, value in notes.items():
                setattr(session, field, value)
        if summary and not session.zoom_summary_raw:
            session.zoom_summary_raw = summary
        if not session.zoom_meeting_uuid:
            session.zoom_meeting_uuid = event.meeting_uuid
        if booked and not session.calendar_event_id:
            _link_calendar(session, booked)
        session.save()
        outcome = ZoomMeetingEvent.Outcome.NOTES_FILLED if notes else ZoomMeetingEvent.Outcome.LINKED
    else:
        start, end = (booked["start"], booked["end"]) if booked else (wall_start, wall_end)
        session = Session(
            user=user,
            student=student,
            session_date=start,
            session_start_time=start,
            session_end_time=end,
            is_no_show=no_show,
            zoom_meeting_uuid=event.meeting_uuid,
            zoom_summary_raw=summary,
            **(notes or {}),
        )
        if booked:
            _link_calendar(session, booked)
        session.save()
        outcome = ZoomMeetingEvent.Outcome.NO_SHOW if no_show else ZoomMeetingEvent.Outcome.LOGGED

    event.session = session
    event.outcome = outcome
    event.status = ZoomMeetingEvent.Status.DONE
    event.last_error = ""
    return str(outcome)


def has_notes(session: Session) -> bool:
    return any((getattr(session, field) or "").strip() for field in NOTE_FIELDS)


def _link_calendar(session: Session, booked: dict) -> None:
    session.calendar_event_id = booked["event_id"]
    session.calendar_recurring_id = booked["recurring_id"]
    session.calendar_html_link = booked["html_link"] or None


# --- Matching ---------------------------------------------------------------


def _wall(date_str: str, time_str: str) -> datetime:
    return datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=timezone.utc)


def _names(student) -> set[str]:
    # The same rule as the Sessions page: an event titled "Sam Smith - Tuition"
    # or "Sam - Tuition" is Sam's.
    return {f"{student.first_name} {student.last_name}", student.first_name}


def find_calendar_event(user, student, real_start: datetime, wall_start: datetime) -> dict | None:
    """The student's Tutoring calendar event closest to the meeting, if within
    MATCH_TOLERANCE, as {event_id, recurring_id, html_link, start, end} with
    wall-clock times. None if Google isn't connected or can't be reached."""
    token = GoogleCalendarToken.objects.filter(user=user).first()
    if not token or not token.is_connected:
        return None
    window = services.MATCH_TOLERANCE + timedelta(minutes=30)
    try:
        events = calendar.fetch_events(user, real_start - window, real_start + window)
    except Exception:
        logger.warning("Couldn't read Google Calendar to match a Zoom lesson for user %s", user.id, exc_info=True)
        return None

    names = _names(student)
    best, best_gap = None, None
    for raw in events:
        parsed = calendar.parse_event(raw)
        if parsed["all_day"] or parsed["student_name"] not in names or not parsed["start_time"] or not parsed["end_time"]:
            continue
        start = _wall(parsed["date"], parsed["start_time"])
        gap = abs(start - wall_start)
        if gap <= services.MATCH_TOLERANCE and (best_gap is None or gap < best_gap):
            best_gap = gap
            best = {
                "event_id": parsed["event_id"],
                "recurring_id": raw.get("recurringEventId"),
                "html_link": parsed["html_link"],
                "start": start,
                "end": _wall(parsed["date"], parsed["end_time"]),
            }
    return best


def find_session(user, student, booked: dict | None, wall_start: datetime) -> Session | None:
    """A session already logged for this lesson: the one linked to the calendar
    event, else the student's session starting closest to it within MATCH_TOLERANCE."""
    if booked:
        linked = Session.objects.filter(user=user, calendar_event_id=booked["event_id"]).first()
        if linked:
            return linked
    nearby = Session.objects.filter(
        user=user,
        student=student,
        session_start_time__gte=wall_start - services.MATCH_TOLERANCE,
        session_start_time__lte=wall_start + services.MATCH_TOLERANCE,
    )
    return min(nearby, key=lambda s: abs(s.session_start_time - wall_start), default=None)


# --- Catch-up sweep ---------------------------------------------------------


def sweep(user, days: int = SWEEP_DAYS) -> dict:
    """Find the user's lessons from the last `days` days that Zoom held but
    TutorHub hasn't logged, and log them, then retry anything still pending.

    Covers webhook deliveries lost while the server was down, and no-shows,
    which may never get a summary (so never a webhook).
    """
    if not ZoomToken.objects.filter(user=user).exists():
        raise services.NotConnectedError("Zoom isn't connected. Connect it on the Connections page.")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    for student in user.students.filter(is_active=True).exclude(zoom_meeting_id__isnull=True).exclude(zoom_meeting_id=""):
        meeting_id = services.normalize_meeting_id(student.zoom_meeting_id)
        if not meeting_id:
            continue
        try:
            instances = services.list_past_instances(user, meeting_id)
        except services.NotFoundError:
            continue
        for instance in instances:
            try:
                start = services.parse_zoom_time(instance["start_time"])
            except (KeyError, ValueError):
                continue
            if start < since or not instance.get("uuid"):
                continue
            ZoomMeetingEvent.objects.get_or_create(
                meeting_uuid=instance["uuid"],
                defaults={
                    "user": user,
                    "student": student,
                    "meeting_id": meeting_id,
                    "start_time": start,
                    "source": ZoomMeetingEvent.Source.SWEEP,
                },
            )

    counts = {"logged": 0, "no_shows": 0, "notes_filled": 0, "linked": 0, "waiting": 0, "failed": 0}
    count_key = {"no_show": "no_shows"}
    done = []
    pending = ZoomMeetingEvent.objects.filter(user=user, status=ZoomMeetingEvent.Status.PENDING).values_list("id", flat=True)
    for event_id in list(pending):
        outcome = process_event(event_id)
        if outcome:
            counts[count_key.get(outcome, outcome)] += 1
        if outcome in ZoomMeetingEvent.Outcome.values:
            done.append(event_id)

    events = ZoomMeetingEvent.objects.filter(id__in=done, session__isnull=False).select_related("session", "student")
    sessions = [
        {
            "session_id": event.session_id,
            "student_name": f"{event.student.first_name} {event.student.last_name}",
            "start": event.session.session_start_time,
            "outcome": event.outcome,
        }
        for event in sorted(events, key=lambda e: e.session.session_start_time, reverse=True)
    ]
    return {**counts, "sessions": sessions}
