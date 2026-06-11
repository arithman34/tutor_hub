import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PayeeCreate(BaseModel):
    first_name: str = Field(..., description="Payee's first name", examples=["John"])
    last_name: str = Field(..., description="Payee's last name", examples=["Doe"])
    email: EmailStr | None = Field(None, description="Payee's email address", examples=["john@example.com"])
    phone_number: str | None = Field(None, description="Payee's phone number in E.164 format", examples=["+447700900000"])
    bank_reference_pattern: str | None = Field(None, description="Pattern used to match bank transfer references")


class PayeeUpdate(BaseModel):
    first_name: str | None = Field(None, description="Payee's first name", examples=["John"])
    last_name: str | None = Field(None, description="Payee's last name", examples=["Doe"])
    email: EmailStr | None = Field(None, description="Payee's email address", examples=["john@example.com"])
    phone_number: str | None = Field(None, description="Payee's phone number in E.164 format", examples=["+447700900000"])
    bank_reference_pattern: str | None = Field(None, description="Pattern used to match bank transfer references")


class PayeeResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Unique identifier for the payee", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    user_id: uuid.UUID = Field(..., description="ID of the tutor who owns this payee", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    first_name: str = Field(..., description="Payee's first name", examples=["John"])
    last_name: str = Field(..., description="Payee's last name", examples=["Doe"])
    email: str | None = Field(None, description="Payee's email address", examples=["john@example.com"])
    phone_number: str | None = Field(None, description="Payee's phone number in E.164 format", examples=["+447700900000"])
    bank_reference_pattern: str | None = Field(None, description="Pattern used to match bank transfer references")
    created_at: datetime = Field(..., description="Timestamp when the payee was created")
    updated_at: datetime = Field(..., description="Timestamp when the payee was last updated")

    model_config = {"from_attributes": True}
