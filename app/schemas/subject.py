from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(..., description="Name of the subject", examples=["Mathematics"])


class SubjectResponse(BaseModel):
    id: int = Field(..., description="Unique identifier for the subject", examples=[1])
    name: str = Field(..., description="Name of the subject", examples=["Mathematics"])

    model_config = {"from_attributes": True}
