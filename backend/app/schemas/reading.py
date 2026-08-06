import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class BPReadingCreate(BaseModel):
    systolic: int = Field(gt=0,lt=300)
    diastolic: int = Field(gt=0, lt=200)
    heart_rate: int  | None = Field(default=None, gt=0, lt=250)
    recorded_at: datetime | None = None
    source:str = "manual"

    @field_validator("diastolic")
    @classmethod
    def diastolic_must_be_less_than_systolic(cls,v, info):
        systolic = info.data.get("systolic")
        if systolic is not None and v >= systolic:
            raise ValueError("Diastolic must be less than systolic")
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


    class Config:
        from_attributes = True