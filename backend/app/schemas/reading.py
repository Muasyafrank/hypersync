import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BPReadingCreate(BaseModel):
    systolic: int = Field(ge=60, le=260, description="Systolic pressure in mmHg (60-260)")
    diastolic: int = Field(ge=30, le=180, description="Diastolic pressure in mmHg (30-180)")
    heart_rate: int | None = Field(default=None, ge=30, le=220, description="Heart rate in bpm (30-220)")
    recorded_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    rested_before: bool | None = Field(default=None, description="Sat quietly for about 5 minutes first")
    stimulant_before: bool | None = Field(
        default=None, description="Coffee/tea, smoking or exercise in the 30 minutes before"
    )

    @field_validator("diastolic")
    @classmethod
    def diastolic_must_be_less_than_systolic(cls, v: int, info) -> int:
        systolic = info.data.get("systolic")
        if systolic is not None and v >= systolic:
            raise ValueError("Diastolic must be less than systolic")
        return v

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_not_in_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        # Treat a naive datetime as UTC rather than crashing on the comparison.
        reference = v if v.tzinfo else v.replace(tzinfo=UTC)
        if reference > datetime.now(UTC):
            raise ValueError("Reading date/time cannot be in the future")
        return v


class ReadingSummary(BaseModel):
    """Totals across ALL of a patient's readings, without sending them."""

    total: int
    status_counts: dict[str, int]


class BPReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reading_id: uuid.UUID
    patient_id: uuid.UUID
    systolic: int
    diastolic: int
    heart_rate: int | None = None
    recorded_at: datetime
    status: str
    notes: str | None = None
    rested_before: bool | None = None
    stimulant_before: bool | None = None
