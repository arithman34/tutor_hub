from urllib.parse import parse_qs, urlparse

from app.services.google_calendar import (
    build_connect_url,
    build_event_title,
    build_rrule,
    is_connected,
    parse_event,
)


def _requested_scopes() -> set[str]:
    query = parse_qs(urlparse(build_connect_url("state")).query)
    return set(query["scope"][0].split())


def test_connect_url_requests_only_per_resource_scopes():
    # Account-wide scopes would drag the app into sensitive scope verification.
    assert _requested_scopes() == {
        "https://www.googleapis.com/auth/calendar.app.created",
        "https://www.googleapis.com/auth/drive.file",
    }


def test_connect_url_asks_for_offline_access():
    query = parse_qs(urlparse(build_connect_url("state")).query)
    assert query["access_type"] == ["offline"]
    assert query["state"] == ["state"]


class _FakeToken:
    def __init__(self, refresh_token):
        self.refresh_token = refresh_token


def test_is_connected_requires_a_refresh_token():
    assert is_connected(_FakeToken("refresh")) is True


def test_is_connected_rejects_a_disconnected_row():
    # disconnect_token leaves the row behind to preserve tutoring_calendar_id.
    assert is_connected(_FakeToken(None)) is False


def test_is_connected_rejects_missing_token():
    assert is_connected(None) is False


def test_build_event_title_appends_tuition_suffix():
    assert build_event_title("John") == "John - Tuition"


def test_parse_event_extracts_first_name_from_title():
    event = {
        "id": "abc123",
        "summary": "John - Tuition",
        "start": {"dateTime": "2026-06-15T09:00:00+01:00"},
        "end": {"dateTime": "2026-06-15T10:30:00+01:00"},
        "htmlLink": "https://calendar.google.com/event",
    }
    parsed = parse_event(event)
    assert parsed["event_id"] == "abc123"
    assert parsed["summary"] == "John - Tuition"
    assert parsed["student_name"] == "John"
    assert parsed["date"] == "2026-06-15"
    assert parsed["start_time"] == "09:00"
    assert parsed["end_time"] == "10:30"
    assert parsed["all_day"] is False
    assert parsed["html_link"] == "https://calendar.google.com/event"


def test_parse_event_keeps_multi_word_first_name():
    event = {"summary": "Mary Anne - Tuition", "start": {"date": "2026-06-15"}, "end": {"date": "2026-06-16"}}
    assert parse_event(event)["student_name"] == "Mary Anne"


def test_parse_event_handles_all_day_event():
    event = {"summary": "Jane - Tuition", "start": {"date": "2026-06-15"}, "end": {"date": "2026-06-16"}}
    parsed = parse_event(event)
    assert parsed["all_day"] is True
    assert parsed["date"] == "2026-06-15"
    assert parsed["start_time"] == ""
    assert parsed["end_time"] == ""
    assert parsed["student_name"] == "Jane"


def test_parse_event_without_suffix_falls_back_to_full_summary():
    event = {"summary": "Team standup", "start": {"date": "2026-06-15"}}
    assert parse_event(event)["student_name"] == "Team standup"


def test_parse_event_missing_summary_is_blank():
    event = {"start": {"date": "2026-06-15"}}
    parsed = parse_event(event)
    assert parsed["summary"] == ""
    assert parsed["student_name"] == ""


def test_build_rrule_with_end_date_sets_until():
    assert build_rrule(0, 1, "2026-12-31") == "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO;UNTIL=20261231T235959Z"


def test_build_rrule_respects_interval_and_weekday():
    assert build_rrule(6, 2, "2026-12-31") == "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=SU;UNTIL=20261231T235959Z"


def test_build_rrule_without_end_date_repeats_forever():
    assert build_rrule(2, 1) == "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=WE"


def test_build_rrule_blank_end_date_repeats_forever():
    assert build_rrule(2, 1, "") == "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=WE"


def test_build_rrule_none_end_date_repeats_forever():
    assert build_rrule(4, 3, None) == "RRULE:FREQ=WEEKLY;INTERVAL=3;BYDAY=FR"
