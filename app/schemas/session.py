import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    student_id: uuid.UUID = Field(..., description="ID of the student for this session", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    session_date: datetime = Field(..., description="Date of the session", examples=["2024-01-15T00:00:00Z"])
    session_start_time: datetime = Field(..., description="Session start time", examples=["2024-01-15T09:00:00Z"])
    session_end_time: datetime = Field(..., description="Session end time", examples=["2024-01-15T10:00:00Z"])
    planned_minutes: int = Field(..., description="Planned duration of the session in minutes", examples=[60])
    actual_minutes: int | None = Field(None, description="Actual duration of the session in minutes", examples=[60])
    zoom_meeting_uuid: str | None = Field(None, description="Zoom meeting UUID for this session")
    zoom_summary_raw: str | None = Field(None, description="Raw transcript or summary from Zoom")
    work_covered: str | None = Field(None, description="Topics and work covered during the session", examples=["Quadratic equations, factorisation"])
    student_actions: str | None = Field(None, description="Action items assigned to the student", examples=["Complete exercises 1-5 on page 42"])
    tutor_actions: str | None = Field(None, description="Action items for the tutor", examples=["Prepare worksheet on simultaneous equations"])
    next_lesson_focus: str | None = Field(None, description="Planned focus for the next session", examples=["Simultaneous equations"])
    topic_tags: str | None = Field(None, description="Comma-separated topic tags", examples=["algebra,equations,gcse"])
    calendar_event_id: str | None = Field(None, description="Google Calendar event ID")
    calendar_recurring_id: str | None = Field(None, description="Google Calendar recurring event ID")
    calendar_html_link: str | None = Field(None, description="Google Calendar event URL")


class SessionUpdate(BaseModel):
    session_date: datetime | None = Field(None, description="Date of the session", examples=["2024-01-15T00:00:00Z"])
    session_start_time: datetime | None = Field(None, description="Session start time", examples=["2024-01-15T09:00:00Z"])
    session_end_time: datetime | None = Field(None, description="Session end time", examples=["2024-01-15T10:00:00Z"])
    planned_minutes: int | None = Field(None, description="Planned duration of the session in minutes", examples=[60])
    actual_minutes: int | None = Field(None, description="Actual duration of the session in minutes", examples=[55])
    zoom_meeting_uuid: str | None = Field(None, description="Zoom meeting UUID for this session")
    zoom_summary_raw: str | None = Field(None, description="Raw transcript or summary from Zoom")
    work_covered: str | None = Field(None, description="Topics and work covered during the session", examples=["Quadratic equations, factorisation"])
    student_actions: str | None = Field(None, description="Action items assigned to the student", examples=["Complete exercises 1-5 on page 42"])
    tutor_actions: str | None = Field(None, description="Action items for the tutor", examples=["Prepare worksheet on simultaneous equations"])
    next_lesson_focus: str | None = Field(None, description="Planned focus for the next session", examples=["Simultaneous equations"])
    topic_tags: str | None = Field(None, description="Comma-separated topic tags", examples=["algebra,equations,gcse"])
    calendar_event_id: str | None = Field(None, description="Google Calendar event ID")
    calendar_recurring_id: str | None = Field(None, description="Google Calendar recurring event ID")
    calendar_html_link: str | None = Field(None, description="Google Calendar event URL")
    is_paid: bool | None = Field(None, description="Whether this session has been paid for", examples=[False])


class SessionResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Unique identifier for the session", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    user_id: uuid.UUID = Field(..., description="ID of the tutor who owns this session", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    student_id: uuid.UUID = Field(..., description="ID of the student for this session", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    session_date: datetime = Field(..., description="Date of the session", examples=["2024-01-15T00:00:00Z"])
    session_start_time: datetime = Field(..., description="Session start time", examples=["2024-01-15T09:00:00Z"])
    session_end_time: datetime = Field(..., description="Session end time", examples=["2024-01-15T10:00:00Z"])
    planned_minutes: int = Field(..., description="Planned duration of the session in minutes", examples=[60])
    actual_minutes: int | None = Field(None, description="Actual duration of the session in minutes", examples=[55])
    zoom_meeting_uuid: str | None = Field(None, description="Zoom meeting UUID for this session", examples=["abc123def456"])
    zoom_summary_raw: str | None = Field(None, description="Raw transcript or summary from Zoom")
    work_covered: str | None = Field(None, description="Topics and work covered during the session", examples=["Quadratic equations, factorisation"])
    student_actions: str | None = Field(None, description="Action items assigned to the student", examples=["Complete exercises 1-5 on page 42"])
    tutor_actions: str | None = Field(None, description="Action items for the tutor", examples=["Prepare worksheet on simultaneous equations"])
    next_lesson_focus: str | None = Field(None, description="Planned focus for the next session", examples=["Simultaneous equations"])
    topic_tags: str | None = Field(None, description="Comma-separated topic tags", examples=["algebra,equations,gcse"])
    calendar_event_id: str | None = Field(None, description="Google Calendar event ID")
    calendar_recurring_id: str | None = Field(None, description="Google Calendar recurring event ID")
    calendar_html_link: str | None = Field(None, description="Google Calendar event URL")
    is_paid: bool = Field(..., description="Whether this session has been paid for", examples=[False])
    ilp_generated_at: datetime | None = Field(None, description="Timestamp when the ILP was generated for this session")
    created_at: datetime = Field(..., description="Timestamp when the session was created")
    updated_at: datetime | None = Field(None, description="Timestamp when the session was last updated")

    model_config = {"from_attributes": True}
