import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.treatment_review import DISCLAIMER


class WeekOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: date
    end: date
    reading_count: int
    avg_systolic: float | None
    avg_diastolic: float | None
    status: str


class AdherenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answered: int
    missed: int
    status: str


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    hurried: int
    caution: bool


class ReviewRecordOut(BaseModel):
    review_id: uuid.UUID
    reviewed_at: datetime
    clinician_name: str | None
    note: str | None
    flag_kind: str | None
    flag_level: str | None


class TreatmentReviewOut(BaseModel):
    """What the clinician sees on a patient's page."""

    model_config = ConfigDict(from_attributes=True)

    flagged: bool
    active: bool
    kind: str | None
    level: str | None
    headline: str | None
    weeks: list[WeekOut]
    adherence: AdherenceOut
    measurement: MeasurementOut
    confirm_first: list[str]
    contributors: list[str]
    snoozed_until: datetime | None
    last_reviewed_at: datetime | None
    recent_reviews: list[ReviewRecordOut] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class TreatmentReviewBrief(BaseModel):
    """The small version shown as a badge in the patient list."""

    kind: str
    level: str


class MarkReviewedIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = Field(default=None)
