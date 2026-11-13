"""Zoom's webhook: checking its signature, and turning a summary event into a
ZoomMeetingEvent for autolog to process."""

import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.db import IntegrityError

from students.models import Student

from .models import ZoomMeetingEvent, ZoomToken
from .services import normalize_meeting_id, parse_zoom_time

logger = logging.getLogger(__name__)

# Zoom's requests are signed with their timestamp; refuse old ones so a captured
# request can't be replayed later.
MAX_AGE_SECONDS = 300


def _hmac(message: str) -> str:
    return hmac.new(settings.ZOOM_WEBHOOK_SECRET_TOKEN.encode(), message.encode(), hashlib.sha256).hexdigest()


def is_valid_signature(body: bytes, timestamp: str | None, signature: str | None, now: float | None = None) -> bool:
    """Zoom signs "v0:{timestamp}:{raw body}" with the app's Secret Token."""
    if not settings.ZOOM_WEBHOOK_SECRET_TOKEN or not timestamp or not signature:
        return False
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False
    if sent_at > 10**12:  # milliseconds
        sent_at //= 1000
    if abs((now if now is not None else time.time()) - sent_at) > MAX_AGE_SECONDS:
        return False
    expected = "v0=" + _hmac(f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}")
    return hmac.compare_digest(expected, signature)


def url_validation_response(plain_token: str) -> dict:
    """The reply to Zoom's endpoint.url_validation check.

    Only ever sent for a request whose signature checked out: answering
    unsigned ones would let anyone have TutorHub sign text with the secret.
    """
    return {"plainToken": plain_token, "encryptedToken": _hmac(plain_token)}


def find_student(meeting_id: str) -> Student | None:
    """The student whose Zoom meeting this is, among tutors with Zoom connected.

    Zoom shows IDs with spaces ("123 4567 8901"), so compare digits only. Two
    matches would mean the same meeting ID on two students: skip rather than guess.
    """
    digits = normalize_meeting_id(meeting_id)
    if not digits:
        return None
    connected = ZoomToken.objects.values_list("user_id", flat=True)
    candidates = Student.objects.filter(user_id__in=connected, zoom_meeting_id__isnull=False).exclude(zoom_meeting_id="")
    matches = [s for s in candidates if normalize_meeting_id(s.zoom_meeting_id) == digits]
    if len(matches) > 1:
        logger.warning("Zoom meeting %s matches %d students; not logging it", digits, len(matches))
        return None
    return matches[0] if matches else None


def record_summary_event(payload: dict) -> ZoomMeetingEvent | None:
    """A ZoomMeetingEvent for a meeting.summary_completed payload, or None if it
    isn't a known student's meeting or was already recorded."""
    obj = (payload.get("payload") or {}).get("object") or {}
    meeting_id = str(obj.get("meeting_id") or obj.get("id") or "")
    meeting_uuid = obj.get("meeting_uuid") or obj.get("uuid")
    if not meeting_uuid:
        logger.warning("Zoom summary event without a meeting UUID")
        return None

    student = find_student(meeting_id)
    if not student:
        logger.info("Zoom summary for meeting %s matches no student; ignoring", normalize_meeting_id(meeting_id))
        return None

    start = None
    if obj.get("meeting_start_time"):
        try:
            start = parse_zoom_time(obj["meeting_start_time"])
        except ValueError:
            pass

    try:
        event, created = ZoomMeetingEvent.objects.get_or_create(
            meeting_uuid=meeting_uuid,
            defaults={
                "user": student.user,
                "student": student,
                "meeting_id": normalize_meeting_id(meeting_id),
                "start_time": start,
                "source": ZoomMeetingEvent.Source.WEBHOOK,
            },
        )
    except IntegrityError:  # a simultaneous duplicate delivery won the race
        return None
    if not created and event.status != ZoomMeetingEvent.Status.PENDING:
        return None
    return event
