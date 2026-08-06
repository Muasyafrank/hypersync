from datetime import date
from pydantic import BaseModel

class DailyAverage(BaseModel):
    date:date
    avg_systolic:float
    avg_diastolic:float
    reading_count:int
    status: str

class TrendSummary(BaseModel):
    period_days: int
    reading_count: int
    avg_systolic: float | None
    avg_diastolic: float | None
    avg_heart_rate: float | None
    status: str
    daily_breakdown: list[DailyAverage]