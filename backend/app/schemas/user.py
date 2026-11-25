import uuid
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.core.localtime import DEFAULT_TIMEZONE_NAME, local_day
from app.models.user import SexEnum, UserRole
from app.schemas.treatment_review import TreatmentReviewBrief

# Trimmed, non-empty, bounded: stops "   " from registering as a blank name.
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class UserRegister(BaseModel):
    full_name: PersonName
    email: EmailStr
    password: str = Field(min_length=8)
    date_of_birth: date | None = None
    sex: SexEnum | None = None
    timezone: str = Field(default=DEFAULT_TIMEZONE_NAME, min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_an_iana_name(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError("timezone must be a valid IANA timezone name") from exc
        return value

    @model_validator(mode="after")
    def date_of_birth_cannot_be_in_the_patients_future(self):
        if self.date_of_birth is not None:
            patient_today = local_day(datetime.now(UTC), ZoneInfo(self.timezone))
            if self.date_of_birth > patient_today:
                raise ValueError("date of birth cannot be in the future")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    created_at: datetime


class ClinicianCreate(BaseModel):
    full_name: PersonName
    email: EmailStr
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    full_name: PersonName | None = None
    email: EmailStr | None = None
    role: UserRole | None = None
    password: str | None = Field(default=None, min_length=8)


class UserDetailOut(UserOut):
    date_of_birth: date | None = None
    sex: SexEnum | None = None
    timezone: str | None = None
    reading_count: int | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8)


class LatestReading(BaseModel):
    systolic: int
    diastolic: int
    status: str
    recorded_at: datetime


class PatientSummaryOut(BaseModel):
    """Row shown in the clinician's patient list."""

    user_id: uuid.UUID
    full_name: str
    email: EmailStr
    reading_count: int = 0
    latest: LatestReading | None = None
    # Set only when the patient is flagged for a treatment review and it hasn't just been reviewed.
    treatment_review: TreatmentReviewBrief | None = None
