import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    first_name: str = Field(..., description="Student's first name", examples=["John"])
    last_name: str = Field(..., description="Student's last name", examples=["Doe"])
    payee_id: uuid.UUID | None = Field(
        None, description="ID of the payee responsible for this student", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
    )
    level: str | None = Field(None, description="Student's academic level", examples=["GCSE"])
    hourly_rate: float | None = Field(None, description="Hourly tutoring rate in GBP", examples=[50.0])
    zoom_meeting_id: str | None = Field(None, description="Zoom meeting ID for recurring sessions")
    google_doc_id: str | None = Field(None, description="Google Doc ID for student notes")
    onedrive_shared_link: str | None = Field(None, description="OneDrive shared link for student resources")


class StudentUpdate(BaseModel):
    first_name: str | None = Field(None, description="Student's first name", examples=["John"])
    last_name: str | None = Field(None, description="Student's last name", examples=["Doe"])
    payee_id: uuid.UUID | None = Field(
        None, description="ID of the payee responsible for this student", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
    )
    level: str | None = Field(None, description="Student's academic level", examples=["GCSE"])
    hourly_rate: float | None = Field(None, description="Hourly tutoring rate in GBP", examples=[50.0])
    zoom_meeting_id: str | None = Field(None, description="Zoom meeting ID for recurring sessions")
    google_doc_id: str | None = Field(None, description="Google Doc ID for student notes")
    onedrive_shared_link: str | None = Field(None, description="OneDrive shared link for student resources")
    is_active: bool | None = Field(None, description="Whether the student is active", examples=[True])


class StudentResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Unique identifier for the student", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    user_id: uuid.UUID = Field(..., description="ID of the tutor who owns this student", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    first_name: str = Field(..., description="Student's first name", examples=["John"])
    last_name: str = Field(..., description="Student's last name", examples=["Doe"])
    payee_id: uuid.UUID | None = Field(
        None, description="ID of the payee responsible for this student", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
    )
    level: str | None = Field(None, description="Student's academic level", examples=["GCSE"])
    hourly_rate: float | None = Field(None, description="Hourly tutoring rate in GBP", examples=[50.0])
    zoom_meeting_id: str | None = Field(None, description="Zoom meeting ID for recurring sessions")
    google_doc_id: str | None = Field(None, description="Google Doc ID for student notes")
    onedrive_shared_link: str | None = Field(None, description="OneDrive shared link for student resources")
    is_active: bool = Field(..., description="Whether the student is active", examples=[True])
    created_at: datetime = Field(..., description="Timestamp when the student was created")
    updated_at: datetime | None = Field(None, description="Timestamp when the student was last updated")

    model_config = {"from_attributes": True}
