from datetime import datetime, timedelta, timezone
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.reading import BPReading
from app.core.bp_classification import classify_bp
from app.schemas.trend import TrendSummary, DailyAverage

def compute_trend(db:Session,patient_id,period_days: int = 7) -> TrendSummary:
    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
    readings = (
        db.query(BPReading)
        .filter(BPReading.patient_id == patient_id, BPReading.recorded_at >= cutoff)
        .order_by(BPReading.recorded_at.asc())
        .all()
    )
    if not readings:
        return TrendSummary(
            period_days=period_days,
            reading_count=0,
            avg_systolic=None,
            avg_diastolic=None,
            avg_heart_rate=None,
            status="no_data",
            daily_breakdown=[],
        )
    avg_systolic = sum(r.systolic for r in readings) / len(readings)
    avg_diastolic = sum(r.diastolic for r in readings) / len(readings)
    heart_rates = [r.heart_rate for r in readings if r.heart_rate is not None]
    avg_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else None

    overall_status = classify_bp(round(avg_systolic), round(avg_diastolic))

    by_day = defaultdict(list)
    for r in readings:
        day = r.recorded_at.date()
        by_day[day].append(r)


    daily_breakdown = []
    for day in sorted(by_day.keys()):
        day_readings = by_day[day]
        day_avg_sys = sum(r.systolic for r in day_readings) / len(day_readings)
        day_avg_dia = sum(r.diastolic for r in day_readings) / len(day_readings)
        daily_breakdown.append(
            DailyAverage(
                date=day,
                avg_systolic=round(day_avg_sys, 1),
                avg_diastolic=round(day_avg_dia, 1),
                reading_count=len(day_readings),
                status=classify_bp(round(day_avg_sys), round(day_avg_dia)),
            )
        )

    return TrendSummary(
        period_days=period_days,
        reading_count=len(readings),
        avg_systolic=round(avg_systolic, 1),
        avg_diastolic=round(avg_diastolic, 1),
        avg_heart_rate=round(avg_heart_rate, 1) if avg_heart_rate else None,
        status=overall_status,
        daily_breakdown=daily_breakdown,
    )   

