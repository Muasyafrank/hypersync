import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class BPReadingCreate(BaseModel):
    systolic: int = Field(ge=60, le=260, description="Systolic pressure in mmHg (60-260)")
    diastolic: int = Field(ge=30, le=180, description="Diastolic pressure in mmHg (30-180)")
    heart_rate: int | None = Field(default=None, ge=30, le=220, description= "Heart rate in bpm (30-220)")
    recorded_at: datetime | None = None
    notes: str | None = None

    @field_validator("diastolic")
    @classmethod
    def diastolic_must_be_less_than_systolic(cls,v, info):
        systolic = info.data.get("systolic")
        if systolic is not None and v >= systolic:
            raise ValueError("Diastolic must be less than systolic")
        return v
    @field_validator("recorded_at")
    @classmethod
    def recorded_at_not_in_future(cls, v):
        if v is not None:
            from datetime import datetime, timezone
            if v > datetime.now(timezone.utc):
                raise ValueError("Reading date/time cannot be in future")
            return v


class BPReadingOut(BaseModel):
    reading_id: uuid.UUID
    patient_id: uuid.UUID
    systolic: int
    diastolic: int
    heart_rate: int | None
    recorded_at: datetime
    source: str
    status: str
    notes: str


    class Config:
        from_attributes = True