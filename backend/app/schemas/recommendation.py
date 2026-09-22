import uuid
from datetime import datetime
from pydantic import BaseModel


class RecommendationOut(BaseModel):
    recommendation_id: uuid.UUID
    message: str
    based_on_trend: str | None
    confidence: float | None = None
    source: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True