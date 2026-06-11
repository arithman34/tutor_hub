import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User's email address", examples=["john@example.com"])
    password: str = Field(..., description="User's password", min_length=8, examples=["S3cur3P@ss!"])
    first_name: str = Field(..., description="User's first name", examples=["John"])
    last_name: str = Field(..., description="User's last name", examples=["Doe"])
    role: str = Field(..., description="User's role in the system", examples=["admin", "tutor"])
    is_active: bool = Field(default=True, description="Whether the user account is active", examples=[True])


class UserUpdate(BaseModel):
    email: EmailStr | None = Field(None, description="User's email address", examples=["john@example.com"])
    password: str | None = Field(None, description="User's password", min_length=8, examples=["S3cur3P@ss!"])
    first_name: str | None = Field(None, description="User's first name", examples=["John"])
    last_name: str | None = Field(None, description="User's last name", examples=["Doe"])
    role: str | None = Field(None, description="User's role in the system", examples=["admin", "tutor"])
    is_active: bool | None = Field(None, description="Whether the user account is active", examples=[True])


class UserResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Unique identifier for the user", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    email: EmailStr = Field(..., description="User's email address", examples=["john@example.com"])
    first_name: str = Field(..., description="User's first name", examples=["John"])
    last_name: str = Field(..., description="User's last name", examples=["Doe"])
    role: str = Field(..., description="User's role in the system", examples=["admin", "tutor"])
    is_active: bool = Field(..., description="Whether the user account is active", examples=[True])
    created_at: datetime = Field(..., description="Timestamp when the user was created")
    updated_at: datetime = Field(..., description="Timestamp when the user was last updated")

    model_config = {"from_attributes": True}
