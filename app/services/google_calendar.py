from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.google_calendar_token import GoogleCalendarToken

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
_CALENDARS_URL = "https://www.googleapis.com/calendar/v3/calendars"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_PRIMARY_CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary"

_SCOPE = " ".join([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
])

_DAY_RRULE = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

# All tutoring events live on a dedicated "Tutoring" calendar (created on demand)
# rather than the user's primary/personal calendar.
_TUTORING_CALENDAR_NAME = "Tutoring"

# Event titles are "{first name} - Tuition" (fixed suffix, not configurable).
_TUITION_SUFFIX = " - Tuition"


def build_event_title(first_name: str) -> str:
    return f"{first_name}{_TUITION_SUFFIX}"

# Two popup reminders on every event: 1 hour and 15 minutes before.
_EVENT_REMINDERS = {
    "useDefault": False,
    "overrides": [
        {"method": "popup", "minutes": 60},
        {"method": "popup", "minutes": 15},
    ],
}


def build_connect_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, user_id, db: AsyncSession) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    result = await db.execute(select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user_id))
    token = result.scalar_one_or_none()

    if token:
        token.access_token = data["access_token"]
        if "refresh_token" in data:
            token.refresh_token = data["refresh_token"]
        token.expires_at = expires_at
        token.updated_at = datetime.now(timezone.utc)
    else:
        token = GoogleCalendarToken(
            user_id=user_id,
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )
        db.add(token)

    await db.commit()


async def _get_valid_access_token(token: GoogleCalendarToken, db: AsyncSession) -> str:
    if datetime.now(timezone.utc) < token.expires_at:
        return token.access_token

    if not token.refresh_token:
        raise ValueError("Google Calendar connection expired — please reconnect.")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code == 400:
        # Refresh token was rejected (revoked, or expired — e.g. Google auto-expires
        # test-user refresh tokens after 7 days while the OAuth app is unpublished).
        await db.delete(token)
        await db.commit()
        raise ValueError("Google Calendar connection expired — please reconnect.")

    resp.raise_for_status()
    data = resp.json()

    token.access_token = data["access_token"]
    token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    token.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return token.access_token


async def _resolve_token(user_id, db: AsyncSession) -> tuple[str, GoogleCalendarToken]:
    result = await db.execute(select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if not token:
        raise ValueError("Google Calendar not connected.")
    return await _get_valid_access_token(token, db), token


async def _fetch_timezone(client: httpx.AsyncClient, access_token: str) -> str:
    resp = await client.get(
        _PRIMARY_CALENDAR_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status_code == 200:
        return resp.json().get("timeZone", "UTC")
    return "UTC"


async def _get_tutoring_calendar_id(
    client: httpx.AsyncClient, headers: dict, *, create: bool
) -> str | None:
    """Return the id of the user's "Tutoring" calendar, creating it if missing.

    When create is False (read paths) a missing calendar returns None instead of
    creating one, so we never make an empty calendar just by listing sessions.
    """
    resp = await client.get(_CALENDAR_LIST_URL, headers=headers)
    resp.raise_for_status()
    for item in resp.json().get("items", []):
        if item.get("summary") == _TUTORING_CALENDAR_NAME:
            return item["id"]

    if not create:
        return None

    resp = await client.post(
        _CALENDARS_URL,
        json={"summary": _TUTORING_CALENDAR_NAME},
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _event_sort_key(event: dict) -> str:
    start = event.get("start", {})
    return start.get("dateTime") or start.get("date") or ""


def parse_event(event: dict) -> dict:
    """Flatten a Google Calendar event into the fields the UI needs."""
    summary = event.get("summary", "") or ""
    start = event.get("start", {})
    end = event.get("end", {})

    if start.get("dateTime"):
        # e.g. "2026-06-15T09:00:00+01:00"
        date_str = start["dateTime"][:10]
        start_time = start["dateTime"][11:16]
        end_time = end.get("dateTime", "")[11:16] if end.get("dateTime") else ""
        all_day = False
    else:
        date_str = start.get("date", "")
        start_time = ""
        end_time = ""
        all_day = True

    # Title convention is "{first name} - Tuition" — pull the first name back out.
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


async def fetch_events(
    user_id,
    time_min: datetime,
    time_max: datetime,
    db: AsyncSession,
) -> list[dict]:
    """Fetch all events on the Tutoring calendar in the given window, sorted
    ascending by start time. Returns an empty list if the calendar doesn't exist
    yet."""
    access_token, _ = await _resolve_token(user_id, db)
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 2500,
    }

    all_events: list[dict] = []
    async with httpx.AsyncClient() as client:
        cal_id = await _get_tutoring_calendar_id(client, headers, create=False)
        if not cal_id:
            return []

        page_params = params
        while True:
            ev_resp = await client.get(
                _EVENTS_URL.format(calendar_id=cal_id),
                params=page_params,
                headers=headers,
            )
            if ev_resp.status_code != 200:
                break
            data = ev_resp.json()
            all_events.extend(data.get("items", []))
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            page_params = {**params, "pageToken": next_token}

    all_events.sort(key=_event_sort_key)
    return all_events


async def get_upcoming_events(user_id, db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    return await fetch_events(user_id, now, now + timedelta(days=7), db)


async def create_one_off_event(
    user_id,
    summary: str,
    date_str: str,
    start_time: str,
    end_time: str,
    db: AsyncSession,
    location: str | None = None,
) -> dict:
    access_token, _ = await _resolve_token(user_id, db)
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        tz = await _fetch_timezone(client, access_token)
        cal_id = await _get_tutoring_calendar_id(client, headers, create=True)
        body = {
            "summary": summary,
            "start": {"dateTime": f"{date_str}T{start_time}:00", "timeZone": tz},
            "end": {"dateTime": f"{date_str}T{end_time}:00", "timeZone": tz},
            "reminders": _EVENT_REMINDERS,
        }
        if location:
            body["location"] = location
        resp = await client.post(
            _EVENTS_URL.format(calendar_id=cal_id),
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def create_recurring_events(
    user_id,
    summary: str,
    day_configs: list[dict],
    start_date_str: str,
    end_date_str: str,
    interval_weeks: int,
    db: AsyncSession,
    location: str | None = None,
) -> list[dict]:
    """
    Create one recurring event per selected weekday.

    day_configs: [{"weekday": int (0=Mon, 6=Sun), "start": "HH:MM", "end": "HH:MM"}, ...]
    One RRULE event is created per day so each day can have its own start/end time.
    """
    access_token, _ = await _resolve_token(user_id, db)
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)
    until = end_date.strftime("%Y%m%dT235959Z")

    created: list[dict] = []
    async with httpx.AsyncClient() as client:
        tz = await _fetch_timezone(client, access_token)
        headers = {"Authorization": f"Bearer {access_token}"}
        cal_id = await _get_tutoring_calendar_id(client, headers, create=True)

        for config in day_configs:
            weekday = config["weekday"]
            days_ahead = (weekday - start_date.weekday()) % 7
            first = start_date + timedelta(days=days_ahead)

            rrule = f"RRULE:FREQ=WEEKLY;INTERVAL={interval_weeks};BYDAY={_DAY_RRULE[weekday]};UNTIL={until}"
            body = {
                "summary": summary,
                "start": {"dateTime": f"{first.isoformat()}T{config['start']}:00", "timeZone": tz},
                "end": {"dateTime": f"{first.isoformat()}T{config['end']}:00", "timeZone": tz},
                "recurrence": [rrule],
                "reminders": _EVENT_REMINDERS,
            }
            if location:
                body["location"] = location
            resp = await client.post(
                _EVENTS_URL.format(calendar_id=cal_id),
                json=body,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                created.append(resp.json())

    return created
