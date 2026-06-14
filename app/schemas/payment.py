import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    payee_id: uuid.UUID = Field(..., description="ID of the payee receiving the payment", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    amount: float = Field(..., description="Payment amount in GBP (e.g. 50.00)", examples=[50.00])
    payment_date: datetime = Field(..., description="Date the payment was made", examples=["2024-01-15T00:00:00Z"])
    payment_reference: str | None = Field(None, description="Reference for the payment", examples=["INV-2024-001"])


class PaymentUpdate(BaseModel):
    amount: float | None = Field(None, description="Payment amount in GBP (e.g. 50.00)", examples=[50.00])
    payment_date: datetime | None = Field(None, description="Date the payment was made", examples=["2024-01-15T00:00:00Z"])
    payment_reference: str | None = Field(None, description="Reference for the payment")
    truelayer_transaction_id: str | None = Field(None, description="TrueLayer transaction ID once reconciled")


class PaymentResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Unique identifier for the payment", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    user_id: uuid.UUID = Field(..., description="ID of the tutor who owns this payment", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    payee_id: uuid.UUID = Field(..., description="ID of the payee receiving the payment", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    amount: float = Field(..., description="Payment amount in GBP (e.g. 50.00)", examples=[50.00])
    payment_date: datetime = Field(..., description="Date the payment was made", examples=["2024-01-15T00:00:00Z"])
    payment_reference: str | None = Field(None, description="Reference for the payment")
    truelayer_transaction_id: str | None = Field(None, description="TrueLayer transaction ID once reconciled")
    created_at: datetime = Field(..., description="Timestamp when the payment was created")
    updated_at: datetime | None = Field(None, description="Timestamp when the payment was last updated")

    model_config = {"from_attributes": True}
