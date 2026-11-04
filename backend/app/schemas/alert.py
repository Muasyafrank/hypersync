import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    alert_type: str
    message: str
    acknowledged: bool
    created_at: datetime
