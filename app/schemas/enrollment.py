import uuid

from pydantic import BaseModel, Field


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID = Field(..., description="ID of the student enrolling in the subject", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    subject_id: uuid.UUID = Field(..., description="ID of the subject the student is enrolling in", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])


class EnrollmentResponse(BaseModel):
    student_id: uuid.UUID = Field(..., description="ID of the student enrolled in the subject", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    subject_id: uuid.UUID = Field(..., description="ID of the subject the student is enrolled in", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])

    model_config = {"from_attributes": True}
