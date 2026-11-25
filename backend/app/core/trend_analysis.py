from collections import defaultdict
from datetime import UTC, datetime, timedelta, tzinfo

from sqlalchemy.orm import Session

from app.core.bp_classification import NO_DATA, classify_bp
from app.core.localtime import local_day  # noqa: F401  (re-exported: other modules import it from here)
from app.models.reading import BPReading
from app.schemas.trend import DailyAverage, TrendSummary


def latest_reading_time(db: Session, patient_id) -> datetime | None:
    """Timestamp of the patient's most recent reading, or None."""
    row = (
        db.query(BPReading.recorded_at)
        .filter(BPReading.patient_id == patient_id)
        .order_by(BPReading.recorded_at.desc())
        .first()
    )
    return row[0] if row else None


def compute_trend(
    db: Session, patient_id, period_days: int = 7, end: datetime | None = None, tz: tzinfo = UTC
) -> TrendSummary:
    """Summarise the `period_days` ending at `end`.

    With no `end` the window is "the last N days" and has no upper bound, so a
    reading stamped slightly in the future (clock skew) is still counted. An
    explicit `end` is used to describe an older stretch of readings.
    """
    cutoff = (end or datetime.now(UTC)) - timedelta(days=period_days)
    query = db.query(BPReading).filter(BPReading.patient_id == patient_id, BPReading.recorded_at >= cutoff)
    if end is not None:
        query = query.filter(BPReading.recorded_at <= end)
    readings = query.order_by(BPReading.recorded_at.asc()).all()
    return summarize_readings(readings, period_days, tz)


def summarize_readings(readings, period_days: int, tz: tzinfo = UTC) -> TrendSummary:
    """Average the readings overall and per day, with days taken in `tz`."""
    if not readings:
        return TrendSummary(
            period_days=period_days,
            reading_count=0,
            avg_systolic=None,
            avg_diastolic=None,
            avg_heart_rate=None,
            status=NO_DATA,
            daily_breakdown=[],
        )
    avg_systolic = sum(r.systolic for r in readings) / len(readings)
    avg_diastolic = sum(r.diastolic for r in readings) / len(readings)
    heart_rates = [r.heart_rate for r in readings if r.heart_rate is not None]
    avg_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else None

    # Classify the same one-decimal values returned to the user. Otherwise an
    # average such as 149.96 could be displayed as 150.0 while still carrying
    # the lower "elevated" status.
    overall_systolic = round(avg_systolic, 1)
    overall_diastolic = round(avg_diastolic, 1)
    overall_status = classify_bp(overall_systolic, overall_diastolic)

    by_day = defaultdict(list)
    for r in readings:
        by_day[local_day(r.recorded_at, tz)].append(r)

    daily_breakdown = []
    for day in sorted(by_day.keys()):
        day_readings = by_day[day]
        day_avg_sys = round(sum(r.systolic for r in day_readings) / len(day_readings), 1)
        day_avg_dia = round(sum(r.diastolic for r in day_readings) / len(day_readings), 1)
        daily_breakdown.append(
            DailyAverage(
                date=day,
                avg_systolic=day_avg_sys,
                avg_diastolic=day_avg_dia,
                reading_count=len(day_readings),
                status=classify_bp(day_avg_sys, day_avg_dia),
            )
        )

    return TrendSummary(
        period_days=period_days,
        reading_count=len(readings),
        avg_systolic=overall_systolic,
        avg_diastolic=overall_diastolic,
        avg_heart_rate=round(avg_heart_rate, 1) if avg_heart_rate is not None else None,
        status=overall_status,
        daily_breakdown=daily_breakdown,
    )
