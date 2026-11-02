import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models.user import SexEnum, UserRole

# Trimmed, non-empty, bounded: stops "   " from registering as a blank name.
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class UserRegister(BaseModel):
    full_name: PersonName
    email: EmailStr
    password: str = Field(min_length=8)
    date_of_birth: date | None = None
    sex: SexEnum | None = None


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
