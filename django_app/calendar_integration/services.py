from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from django.conf import settings

from .models import GoogleCalendarToken

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CALENDARS_URL = "https://www.googleapis.com/calendar/v3/calendars"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

# Per-resource rather than account-wide: calendar.app.created reaches only
# calendars this app made. Request nothing the app doesn't use, since every
# scope shows on Google's consent screen and in OAuth verification.
_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_DAY_RRULE = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

_TUTORING_CALENDAR_NAME = "Tutoring"
_TUITION_SUFFIX = " - Tuition"

_EVENT_REMINDERS = {
    "useDefault": False,
    "overrides": [
        {"method": "popup", "minutes": 60},
        {"method": "popup", "minutes": 15},
    ],
}


def build_event_title(first_name: str) -> str:
    return f"{first_name}{_TUITION_SUFFIX}"


def build_connect_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, user) -> GoogleCalendarToken:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    token, _ = GoogleCalendarToken.objects.get_or_create(user=user, defaults={"access_token": "", "expires_at": expires_at})
    token.access_token = data["access_token"]
    if "refresh_token" in data:
        token.refresh_token = data["refresh_token"]
    token.expires_at = expires_at
    token.save()
    return token


def disconnect_token(token: GoogleCalendarToken) -> None:
    """Clear the credentials but keep the row, so tutoring_calendar_id survives.

    calendar.app.created can't search the user's calendarList, so the stored id
    is our only handle on the Tutoring calendar. Deleting it would mean the next
    reconnect silently created a second calendar and orphaned every event on the
    first one.
    """
    token.access_token = ""
    token.refresh_token = None
    token.expires_at = datetime.now(timezone.utc)
    token.save()


def _get_valid_access_token(token: GoogleCalendarToken) -> str:
    if datetime.now(timezone.utc) < token.expires_at:
        return token.access_token

    if not token.refresh_token:
        raise ValueError("Google Calendar connection expired — please reconnect.")

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            _TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code == 400:
        # Refresh token was rejected (revoked, or expired).
        disconnect_token(token)
        raise ValueError("Google Calendar connection expired — please reconnect.")

    resp.raise_for_status()
    data = resp.json()

    token.access_token = data["access_token"]
    token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    token.save()

    return token.access_token


def _resolve_token(user) -> tuple[str, GoogleCalendarToken]:
    token = GoogleCalendarToken.objects.filter(user=user).first()
    if not token or not token.is_connected:
        raise ValueError("Google Calendar not connected.")
    return _get_valid_access_token(token), token


def _create_tutoring_calendar(client: httpx.Client, headers: dict) -> str:
    resp = client.post(_CALENDARS_URL, json={"summary": _TUTORING_CALENDAR_NAME, "timeZone": settings.GOOGLE_CALENDAR_TIMEZONE}, headers=headers)
    resp.raise_for_status()
    return resp.json()["id"]


def _resolve_calendar_id(client: httpx.Client, headers: dict, token: GoogleCalendarToken, *, create: bool) -> str | None:
    """Return the Tutoring calendar id, creating the calendar on first use.

    The id stored on the token row is the only record of which calendar is ours:
    calendar.app.created grants no calendarList access, so there is no way to
    find the calendar again by name.
    """
    if token.tutoring_calendar_id:
        return token.tutoring_calendar_id

    if not create:
        return None

    cal_id = _create_tutoring_calendar(client, headers)
    token.tutoring_calendar_id = cal_id
    token.save()
    return cal_id


class CalendarUnreachableError(Exception):
    """Google rejected the Tutoring calendar we have on record."""


def _rebind_calendar_id(client: httpx.Client, headers: dict, token: GoogleCalendarToken) -> str:
    cal_id = _create_tutoring_calendar(client, headers)
    token.tutoring_calendar_id = cal_id
    token.save()
    return cal_id


def _post_event(client: httpx.Client, headers: dict, token: GoogleCalendarToken, body: dict) -> httpx.Response:
    """Create an event on the Tutoring calendar, retrying once against a fresh
    calendar id if the stored one has gone stale."""
    cal_id = _resolve_calendar_id(client, headers, token, create=True)
    resp = client.post(_EVENTS_URL.format(calendar_id=cal_id), json=body, headers=headers)
    if resp.status_code in (404, 410):
        cal_id = _rebind_calendar_id(client, headers, token)
        resp = client.post(_EVENTS_URL.format(calendar_id=cal_id), json=body, headers=headers)
    return resp


def _event_sort_key(event: dict) -> str:
    start = event.get("start", {})
    return start.get("dateTime") or start.get("date") or ""


def parse_event(event: dict) -> dict:
    """Flatten a Google Calendar event into the fields the UI needs."""
    summary = event.get("summary", "") or ""
    start = event.get("start", {})
    end = event.get("end", {})

    if start.get("dateTime"):
        date_str = start["dateTime"][:10]
        start_time = start["dateTime"][11:16]
        end_time = end.get("dateTime", "")[11:16] if end.get("dateTime") else ""
        all_day = False
    else:
        date_str = start.get("date", "")
        start_time = ""
        end_time = ""
        all_day = True

    student_name = summary[: -len(_TUITION_SUFFIX)] if summary.endswith(_TUITION_SUFFIX) else summary.strip()

    return {
        "event_id": event.get("id", ""),
        "summary": summary,
        "student_name": student_name,
        "date": date_str,
        "start_time": start_time,
        "end_time": end_time,
        "all_day": all_day,
        "html_link": event.get("htmlLink", ""),
    }


def fetch_events(user, time_min: datetime, time_max: datetime) -> list[dict]:
    """Fetch all events on the Tutoring calendar in the given window, sorted
    ascending by start time. Returns an empty list if the calendar doesn't exist yet."""
    access_token, token = _resolve_token(user)
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 2500,
    }

    all_events: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        cal_id = _resolve_calendar_id(client, headers, token, create=False)
        if not cal_id:
            return []

        page_params = params
        while True:
            ev_resp = client.get(_EVENTS_URL.format(calendar_id=cal_id), params=page_params, headers=headers)
            if ev_resp.status_code in (404, 410):
                raise CalendarUnreachableError(
                    "Google can no longer find the Tutoring calendar TutorHub created. "
                    "Reconnecting Google Calendar issues a new grant, which can leave a "
                    "calendar made under the previous one unreadable."
                )
            if ev_resp.status_code == 403:
                raise CalendarUnreachableError("Google denied access to the Tutoring calendar — please reconnect Google Calendar.")
            if ev_resp.status_code != 200:
                raise CalendarUnreachableError(f"Google Calendar returned HTTP {ev_resp.status_code} while listing events.")
            data = ev_resp.json()
            all_events.extend(data.get("items", []))
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            page_params = {**params, "pageToken": next_token}

    all_events.sort(key=_event_sort_key)
    return all_events


def get_upcoming_events(user) -> list[dict]:
    now = datetime.now(timezone.utc)
    return fetch_events(user, now, now + timedelta(days=7))


def create_one_off_event(user, summary: str, date_str: str, start_time: str, end_time: str, location: str | None = None) -> dict:
    access_token, token = _resolve_token(user)
    headers = {"Authorization": f"Bearer {access_token}"}
    tz = settings.GOOGLE_CALENDAR_TIMEZONE
    with httpx.Client(timeout=_TIMEOUT) as client:
        body = {
            "summary": summary,
            "start": {"dateTime": f"{date_str}T{start_time}:00", "timeZone": tz},
            "end": {"dateTime": f"{date_str}T{end_time}:00", "timeZone": tz},
            "reminders": _EVENT_REMINDERS,
        }
        if location:
            body["location"] = location
        resp = _post_event(client, headers, token, body)
        resp.raise_for_status()
        return resp.json()


def build_rrule(weekday: int, interval_weeks: int, end_date_str: str | None = None) -> str:
    """Build a weekly RRULE for a single weekday.

    A blank or missing end date omits UNTIL, so the event repeats indefinitely.
    """
    rrule = f"RRULE:FREQ=WEEKLY;INTERVAL={interval_weeks};BYDAY={_DAY_RRULE[weekday]}"
    if end_date_str:
        until = date.fromisoformat(end_date_str).strftime("%Y%m%dT235959Z")
        rrule += f";UNTIL={until}"
    return rrule


def create_recurring_events(
    user,
    summary: str,
    day_configs: list[dict],
    start_date_str: str,
    end_date_str: str | None,
    interval_weeks: int,
    location: str | None = None,
) -> list[dict]:
    """Create one recurring event per selected weekday.

    day_configs: [{"weekday": int (0=Mon, 6=Sun), "start": "HH:MM", "end": "HH:MM"}, ...]
    """
    access_token, token = _resolve_token(user)
    start_date = date.fromisoformat(start_date_str)
    tz = settings.GOOGLE_CALENDAR_TIMEZONE

    created: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {access_token}"}

        for config in day_configs:
            weekday = config["weekday"]
            days_ahead = (weekday - start_date.weekday()) % 7
            first = start_date + timedelta(days=days_ahead)

            rrule = build_rrule(weekday, interval_weeks, end_date_str)
            body = {
                "summary": summary,
                "start": {"dateTime": f"{first.isoformat()}T{config['start']}:00", "timeZone": tz},
                "end": {"dateTime": f"{first.isoformat()}T{config['end']}:00", "timeZone": tz},
                "recurrence": [rrule],
                "reminders": _EVENT_REMINDERS,
            }
            if location:
                body["location"] = location
            resp = _post_event(client, headers, token, body)
            if resp.status_code in (200, 201):
                created.append(resp.json())

    return created
