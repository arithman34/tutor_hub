from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address", examples=["john@example.com"])
    password: str = Field(..., description="User's password", examples=["S3cur3P@ss!"])


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token", examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    token_type: str = Field(default="bearer", description="Token type", examples=["bearer"])
