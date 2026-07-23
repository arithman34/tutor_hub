from app.services.google_calendar import build_event_title, parse_event


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
