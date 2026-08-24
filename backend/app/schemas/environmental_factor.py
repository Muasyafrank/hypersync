import uuid
from datetime import date, datetime
from pydantic import BaseModel, Field
from app.models.environmental_factor import StressLevel


class EnvironmentalFactorCreate(BaseModel):
    stress_level: StressLevel | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    diet_adherence: bool | None = None
    medication_taken: bool | None = None
    logged_date: date | None = None  # defaults to today if not provided


class EnvironmentalFactorOut(BaseModel):
    factor_id: uuid.UUID
    patient_id: uuid.UUID
    stress_level: StressLevel | None
    sleep_hours: float | None
    diet_adherence: bool | None
    medication_taken: bool | None
    logged_date: date
    created_at: datetime

    class Config:
        from_attributes = True