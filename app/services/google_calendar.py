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
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_PRIMARY_CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary"
_CREATE_EVENT_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

_SCOPE = " ".join([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
])

_DAY_RRULE = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
_TUITION_SUFFIX = " - Tuition"


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
        raise ValueError("Token expired and no refresh token — please reconnect Google Calendar.")

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

    # Title convention is "{First Last} - Tuition" — pull the name back out.
    student_name = summary[: -len(_TUITION_SUFFIX)] if summary.endswith(_TUITION_SUFFIX) else ""

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
    label: str,
    time_min: datetime,
    time_max: datetime,
    db: AsyncSession,
) -> list[dict]:
    """Fetch all events matching `label` across every calendar in the given window,
    sorted ascending by start time."""
    access_token, _ = await _resolve_token(user_id, db)
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "q": label,
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    async with httpx.AsyncClient() as client:
        cal_resp = await client.get(_CALENDAR_LIST_URL, headers=headers)
        cal_resp.raise_for_status()
        calendar_ids = [c["id"] for c in cal_resp.json().get("items", [])]

        all_events: list[dict] = []
        for cal_id in calendar_ids:
            page_params = {**params, "maxResults": 2500}
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
                page_params = {**page_params, "pageToken": next_token}

    all_events.sort(key=_event_sort_key)
    return all_events


async def get_upcoming_events(user_id, label: str, db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    return await fetch_events(user_id, label, now, now + timedelta(days=7), db)


async def create_one_off_event(
    user_id,
    summary: str,
    date_str: str,
    start_time: str,
    end_time: str,
    db: AsyncSession,
) -> dict:
    access_token, _ = await _resolve_token(user_id, db)
    async with httpx.AsyncClient() as client:
        tz = await _fetch_timezone(client, access_token)
        resp = await client.post(
            _CREATE_EVENT_URL,
            json={
                "summary": summary,
                "start": {"dateTime": f"{date_str}T{start_time}:00", "timeZone": tz},
                "end": {"dateTime": f"{date_str}T{end_time}:00", "timeZone": tz},
            },
            headers={"Authorization": f"Bearer {access_token}"},
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

        for config in day_configs:
            weekday = config["weekday"]
            days_ahead = (weekday - start_date.weekday()) % 7
            first = start_date + timedelta(days=days_ahead)

            rrule = f"RRULE:FREQ=WEEKLY;INTERVAL={interval_weeks};BYDAY={_DAY_RRULE[weekday]};UNTIL={until}"
            resp = await client.post(
                _CREATE_EVENT_URL,
                json={
                    "summary": summary,
                    "start": {"dateTime": f"{first.isoformat()}T{config['start']}:00", "timeZone": tz},
                    "end": {"dateTime": f"{first.isoformat()}T{config['end']}:00", "timeZone": tz},
                    "recurrence": [rrule],
                },
                headers=headers,
            )
            if resp.status_code in (200, 201):
                created.append(resp.json())

    return created
