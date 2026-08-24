import uuid
from datetime import datetime
from pydantic import BaseModel


class AlertOut(BaseModel):
    alert_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    alert_type: str
    message: str
    acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True