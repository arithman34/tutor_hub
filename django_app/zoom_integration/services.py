"""Zoom OAuth and the two API calls TutorHub makes: a meeting's past instances,
and an instance's AI Companion summary."""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlencode

import httpx
from django.conf import settings
from django.core import signing
from django.db import transaction

from .models import ZoomToken

logger = logging.getLogger(__name__)

_AUTH_URL = "https://zoom.us/oauth/authorize"
_TOKEN_URL = "https://zoom.us/oauth/token"
_REVOKE_URL = "https://zoom.us/oauth/revoke"
_API_URL = "https://api.zoom.us/v2"

# The scopes the Zoom app is configured with. Zoom takes them from the app's
# settings, not the connect URL, so this list is documentation that a test
# checks against the privacy policy. Change both together.
SCOPES = ("meeting:read:list_past_instances", "meeting:read:summary", "meeting:read:past_meeting")

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Refresh a little early, so a token can't expire between the check and the call.
_EXPIRY_MARGIN = timedelta(seconds=60)

# How far a past meeting's start may be from the session's start and still count as that lesson.
MATCH_TOLERANCE = timedelta(minutes=60)

_STATE_SALT = "zoom-oauth-state"
_STATE_MAX_AGE = 300

# Zoom's error code for a summary the host has deleted (it sits in their trash).
ZOOM_SUMMARY_IN_TRASH = 2305

RECONNECT_MESSAGE = "Your Zoom connection has expired. Reconnect Zoom on the Connections page."


class NotConnectedError(Exception):
    """No usable Zoom connection: never connected, or Zoom refused the refresh token."""


class NotFoundError(Exception):
    """Zoom answered, but there's nothing to fetch. The message says why, for the user."""


class ZoomAPIError(Exception):
    """Zoom couldn't be reached or answered with an error."""


# --- OAuth ------------------------------------------------------------------


def sign_connect_state(user) -> str:
    """The OAuth `state`: a signed, time-limited token naming the user.

    Same approach as calendar_integration: no cookie or server-side session
    is needed to survive the hop to Zoom and back.
    """
    return signing.dumps({"user_id": str(user.id), "nonce": secrets.token_urlsafe(16)}, salt=_STATE_SALT)


def read_connect_state(state: str) -> str:
    """The user id inside a state from sign_connect_state. Raises signing.BadSignature
    (SignatureExpired is a subclass) if it was forged, altered or is too old."""
    return signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)["user_id"]


def build_connect_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.ZOOM_CLIENT_ID,
        "redirect_uri": settings.ZOOM_REDIRECT_URI,
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def _client_auth() -> tuple[str, str]:
    # Zoom takes the client credentials as HTTP Basic auth, not in the form body.
    return (settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)


def _expires_at(expires_in: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in) - _EXPIRY_MARGIN


def exchange_code(code: str, user) -> ZoomToken:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            _TOKEN_URL,
            auth=_client_auth(),
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.ZOOM_REDIRECT_URI},
        )
        resp.raise_for_status()
        data = resp.json()

    token, _ = ZoomToken.objects.update_or_create(
        user=user,
        defaults={
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": _expires_at(data["expires_in"]),
        },
    )
    return token


def disconnect(user) -> None:
    """Revoke the token with Zoom (best effort) and forget it."""
    token = ZoomToken.objects.filter(user=user).first()
    if not token:
        return
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            client.post(_REVOKE_URL, auth=_client_auth(), data={"token": token.access_token})
    except httpx.HTTPError:
        # The local token is gone either way; the user can also remove the app in Zoom.
        logger.warning("Revoking the Zoom token failed for user %s", user.id, exc_info=True)
    token.delete()


def _access_token(user) -> str:
    """A valid access token, refreshing it if needed.

    Zoom rotates the refresh token on every refresh, so the new one must be
    saved. The row is locked while refreshing: two requests refreshing at once
    would otherwise both spend the same refresh token, and one would lose.
    """
    with transaction.atomic():
        token = ZoomToken.objects.select_for_update().filter(user=user).first()
        if not token:
            raise NotConnectedError("Zoom isn't connected. Connect it on the Connections page.")
        if datetime.now(timezone.utc) < token.expires_at:
            return token.access_token

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    _TOKEN_URL,
                    auth=_client_auth(),
                    data={"grant_type": "refresh_token", "refresh_token": token.refresh_token},
                )
        except httpx.HTTPError as exc:
            raise ZoomAPIError("Couldn't reach Zoom.") from exc

        if resp.status_code in (400, 401):
            # Expired (90 days unused), revoked, or the app was removed in Zoom.
            # Raise after the block: raising inside atomic() would roll the delete back.
            token.delete()
        elif resp.is_error:
            raise ZoomAPIError(f"Zoom refused to refresh the connection ({resp.status_code}).")
        else:
            data = resp.json()
            token.access_token = data["access_token"]
            token.refresh_token = data["refresh_token"]
            token.expires_at = _expires_at(data["expires_in"])
            token.save()
            return token.access_token

    # Only a rejected refresh gets here.
    raise NotConnectedError(RECONNECT_MESSAGE)


def _get(user, path: str) -> httpx.Response:
    headers = {"Authorization": f"Bearer {_access_token(user)}"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(f"{_API_URL}{path}", headers=headers)
    except httpx.HTTPError as exc:
        raise ZoomAPIError("Couldn't reach Zoom.") from exc
    if resp.status_code == 401:
        raise NotConnectedError(RECONNECT_MESSAGE)
    return resp


def _zoom_error(resp: httpx.Response, action: str) -> "ZoomAPIError":
    """A ZoomAPIError saying what failed, with Zoom's own explanation when it gave one."""
    logger.error("Zoom %s failed (%s): %s", action, resp.status_code, resp.text[:500])
    message = f"Zoom returned an error ({resp.status_code}) {action}."
    try:
        reason = resp.json().get("message")
    except (ValueError, AttributeError):
        reason = None
    if reason:
        message = f"{message[:-1]}: {reason}"
    return ZoomAPIError(message)


def _zoom_code(resp: httpx.Response) -> int | None:
    try:
        return resp.json().get("code")
    except (ValueError, AttributeError):
        return None


# --- Meetings ---------------------------------------------------------------


def normalize_meeting_id(meeting_id: str | None) -> str:
    """Zoom shows meeting IDs as "123 4567 8901"; the API wants the digits."""
    return re.sub(r"\D", "", meeting_id or "")


def encode_meeting_uuid(uuid: str) -> str:
    """Zoom asks for UUIDs starting with "/" or containing "//" to be encoded twice."""
    encoded = quote(uuid, safe="")
    if uuid.startswith("/") or "//" in uuid:
        encoded = quote(encoded, safe="")
    return encoded


def parse_zoom_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def to_wall_clock(moment: datetime) -> datetime:
    """A real instant as TutorHub's wall-clock time.

    Sessions store the local time the lesson was at, labelled UTC (see the SPA's
    format.ts): a 16:00 lesson in British Summer Time is saved as 16:00Z, not
    15:00Z. Zoom sends real UTC, so convert before comparing or saving.
    """
    local = moment.astimezone(ZoneInfo(settings.GOOGLE_CALENDAR_TIMEZONE))
    return local.replace(tzinfo=timezone.utc)


def closest_instance(instances: list[dict], start: datetime) -> dict | None:
    """The instance that started closest to `start` (a wall-clock session time),
    if within MATCH_TOLERANCE."""
    best, best_gap = None, None
    for instance in instances:
        try:
            gap = abs(to_wall_clock(parse_zoom_time(instance["start_time"])) - start)
        except (KeyError, ValueError):
            continue
        if gap <= MATCH_TOLERANCE and (best_gap is None or gap < best_gap):
            best, best_gap = instance, gap
    return best


def list_past_instances(user, meeting_id: str) -> list[dict]:
    """Past occurrences of a meeting, each {"uuid", "start_time"}."""
    resp = _get(user, f"/past_meetings/{normalize_meeting_id(meeting_id)}/instances")
    if resp.status_code == 404:
        raise NotFoundError("Zoom has no past meetings for this student's meeting ID.")
    if resp.is_error:
        raise _zoom_error(resp, "listing past meetings")
    return resp.json().get("meetings", [])


def past_meeting(user, meeting_uuid: str) -> dict:
    """A finished meeting occurrence: start_time, end_time and participants_count among others."""
    resp = _get(user, f"/past_meetings/{encode_meeting_uuid(meeting_uuid)}")
    if resp.status_code == 404:
        raise NotFoundError("Zoom has no record of this meeting yet. It may still be in progress.")
    if resp.is_error:
        raise _zoom_error(resp, "reading the meeting")
    return resp.json()


def find_meeting_uuid(user, meeting_id: str | None, start: datetime) -> str:
    """The UUID of the occurrence of `meeting_id` that matches a lesson starting at `start`."""
    digits = normalize_meeting_id(meeting_id)
    if not digits:
        raise NotFoundError("This student has no Zoom meeting ID. Add it on their profile first.")

    match = closest_instance(list_past_instances(user, digits), start)
    if not match:
        raise NotFoundError("No Zoom meeting started within an hour of this session's start time.")
    return match["uuid"]


def summary_text(data: dict) -> str:
    """Plain text from a meeting_summary response, in the shape of a pasted summary.

    summary_content is the current field. The structured fields are older, but
    still returned for some accounts; prefer the host's edited versions of them.
    """
    content = data.get("summary_content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    edited = data.get("edited_summary") or {}
    details = edited.get("summary_details") or data.get("summary_details") or []
    next_steps = edited.get("next_steps") or data.get("next_steps") or []

    parts = []
    if data.get("summary_title"):
        parts.append(data["summary_title"])
    if data.get("summary_overview"):
        parts.append(f"Overview\n{data['summary_overview']}")
    for detail in details:
        if isinstance(detail, dict) and detail.get("summary"):
            parts.append(f"{detail.get('label', '')}\n{detail['summary']}".strip())
        elif isinstance(detail, str) and detail.strip():
            parts.append(detail.strip())
    if next_steps:
        parts.append("Next steps\n" + "\n".join(f"- {step}" for step in next_steps))
    return "\n\n".join(parts).strip()


def fetch_summary(user, meeting_uuid: str) -> str:
    resp = _get(user, f"/meetings/{encode_meeting_uuid(meeting_uuid)}/meeting_summary")
    if resp.status_code in (400, 404):
        # 404 until the meeting has fully ended and the summary is ready. 400 when
        # summaries are off for the meeting or the account isn't on a paid plan.
        logger.info("Zoom meeting summary unavailable (%s): %s", resp.status_code, resp.text[:500])
        raise NotFoundError(
            "Zoom has no AI summary for this lesson yet. It can take a few minutes after the meeting ends, "
            "and AI Companion meeting summaries must be turned on."
        )
    if resp.status_code == 403 and _zoom_code(resp) == ZOOM_SUMMARY_IN_TRASH:
        raise NotFoundError("This lesson's Zoom summary is in your Zoom trash. Restore it in Zoom, then try again.")
    if resp.is_error:
        raise _zoom_error(resp, "fetching the summary")

    text = summary_text(resp.json())
    if not text:
        raise NotFoundError("Zoom's summary for this lesson is empty.")
    return text
