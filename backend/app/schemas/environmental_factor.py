import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.environmental_factor import IntakeLevel, NoiseLevel, StressLevel, TemperatureFeel


class EnvironmentalFactorCreate(BaseModel):
    stress_level: StressLevel | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    diet_adherence: bool | None = None
    medication_prescribed: bool | None = None
    medication_taken: bool | None = None
    salt_intake: IntakeLevel | None = None
    caffeine_intake: IntakeLevel | None = None
    alcohol_consumed: bool | None = None
    smoked: bool | None = None
    physical_activity_minutes: int | None = Field(default=None, ge=0, le=1440)
    temperature_feel: TemperatureFeel | None = None
    noise_level: NoiseLevel | None = None
    logged_date: date | None = None

    @model_validator(mode="after")
    def require_at_least_one_answer(self):
        """A date on its own is not a lifestyle check-in.

        Keeping this rule in the request schema means every API caller gets the
        same 422 response, instead of relying on the browser to send an answer.
        """
        answers = (
            self.stress_level,
            self.sleep_hours,
            self.diet_adherence,
            self.medication_taken,
            self.salt_intake,
            self.caffeine_intake,
            self.alcohol_consumed,
            self.smoked,
            self.physical_activity_minutes,
            self.temperature_feel,
            self.noise_level,
        )
        if all(answer is None for answer in answers):
            raise ValueError("answer at least one lifestyle or environmental question")
        if self.medication_prescribed is False and self.medication_taken is not None:
            raise ValueError("medication_taken cannot be recorded when no medication is prescribed")
        return self


class EnvironmentalFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_id: uuid.UUID
    patient_id: uuid.UUID
    stress_level: StressLevel | None
    sleep_hours: float | None
    diet_adherence: bool | None
    medication_prescribed: bool | None
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
