import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: uuid.UUID
    message: str
    based_on_trend: str | None
    confidence: float | None = None
    source: str | None = None
    created_at: datetime
