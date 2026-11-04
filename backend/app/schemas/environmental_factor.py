import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.environmental_factor import IntakeLevel, NoiseLevel, StressLevel, TemperatureFeel


class EnvironmentalFactorCreate(BaseModel):
    stress_level: StressLevel | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    diet_adherence: bool | None = None
    medication_taken: bool | None = None
    salt_intake: IntakeLevel | None = None
    caffeine_intake: IntakeLevel | None = None
    alcohol_consumed: bool | None = None
    smoked: bool | None = None
    physical_activity_minutes: int | None = Field(default=None, ge=0, le=1440)
    temperature_feel: TemperatureFeel | None = None
    noise_level: NoiseLevel | None = None
    logged_date: date | None = None


class EnvironmentalFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_id: uuid.UUID
    patient_id: uuid.UUID
    stress_level: StressLevel | None
    sleep_hours: float | None
    diet_adherence: bool | None
    medication_taken: bool | None
    salt_intake: IntakeLevel | None
    caffeine_intake: IntakeLevel | None
    alcohol_consumed: bool | None
    smoked: bool | None
    physical_activity_minutes: int | None
    temperature_feel: TemperatureFeel | None
    noise_level: NoiseLevel | None
    logged_date: date
    created_at: datetime
