import uuid
from datetime import tzinfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.alert_engine import maybe_create_alert
from app.core.bp_classification import CONTROLLED, ELEVATED, HIGH, LOW, classify_bp
from app.core.database import get_db
from app.core.deps import get_timezone, require_clinician, require_patient
from app.core.trend_analysis import compute_trend
from app.models.reading import BPReading
from app.models.user import User
from app.schemas.reading import BPReadingCreate, BPReadingOut, ReadingSummary
from app.schemas.trend import TrendSummary

router = APIRouter(prefix="/readings", tags=["Blood Pressure Readings"])

ALERT_WINDOW_DAYS = 7


def _to_out(reading: BPReading) -> BPReadingOut:
    """Attach the derived status to a stored reading."""
    return BPReadingOut(
        reading_id=reading.reading_id,
        patient_id=reading.patient_id,
        systolic=reading.systolic,
        diastolic=reading.diastolic,
        heart_rate=reading.heart_rate,
        recorded_at=reading.recorded_at,
        notes=reading.notes,
        rested_before=reading.rested_before,
        stimulant_before=reading.stimulant_before,
        status=classify_bp(reading.systolic, reading.diastolic),
    )


def _readings_for(db: Session, patient_id, limit: int | None = None) -> list[BPReading]:
    query = db.query(BPReading).filter(BPReading.patient_id == patient_id).order_by(BPReading.recorded_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def _status_counts(db: Session, patient_id) -> dict[str, int]:
    """Readings per status, without loading the readings themselves.

    Status is derived from the two numbers, not stored, so group by the pair
    (a few hundred distinct values at most) and classify each group once. That
    keeps `classify_bp` the single source of truth for the thresholds.
    """
    rows = (
        db.query(BPReading.systolic, BPReading.diastolic, func.count())
        .filter(BPReading.patient_id == patient_id)
        .group_by(BPReading.systolic, BPReading.diastolic)
        .all()
    )
    counts = {CONTROLLED: 0, ELEVATED: 0, HIGH: 0, LOW: 0}
    for systolic, diastolic, n in rows:
        counts[classify_bp(systolic, diastolic)] += n
    return counts


@router.post("", response_model=BPReadingOut, status_code=status.HTTP_201_CREATED)
def create_reading(
    payload: BPReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    reading = BPReading(
        patient_id=current_user.user_id,
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        heart_rate=payload.heart_rate,
        recorded_at=payload.recorded_at,
        notes=payload.notes,
        rested_before=payload.rested_before,
        stimulant_before=payload.stimulant_before,
    )
    db.add(reading)
    db.flush()

    # Re-evaluate the trend with this reading included, and raise an alert if
    # it pushes the patient into an elevated/high band. The alert is written in
    # the SAME transaction as the reading, so the two can never disagree.
    trend = compute_trend(db, current_user.user_id, period_days=ALERT_WINDOW_DAYS)
    maybe_create_alert(db, current_user.user_id, trend.status, period_days=ALERT_WINDOW_DAYS)

    db.commit()
    db.refresh(reading)
    return _to_out(reading)


@router.get("/me", response_model=list[BPReadingOut])
def get_my_readings(
    limit: int | None = Query(default=None, ge=1, le=500, description="Most recent N readings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    return [_to_out(r) for r in _readings_for(db, current_user.user_id, limit)]


@router.get("/me/summary", response_model=ReadingSummary)
def get_my_reading_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    """Total and per-status counts across every reading (used by the dashboard)."""
    counts = _status_counts(db, current_user.user_id)
    return ReadingSummary(total=sum(counts.values()), status_counts=counts)


@router.get("/me/trend", response_model=TrendSummary)
def get_my_trend(
    period_days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
    tz: tzinfo = Depends(get_timezone),
):
    return compute_trend(db, current_user.user_id, period_days, tz=tz)


@router.get("/patient/{patient_id}", response_model=list[BPReadingOut])
def get_patient_readings(
    patient_id: uuid.UUID,
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    return [_to_out(r) for r in _readings_for(db, patient_id, limit)]


@router.get("/patient/{patient_id}/trend", response_model=TrendSummary)
def get_patient_trend(
    patient_id: uuid.UUID,
    period_days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
    tz: tzinfo = Depends(get_timezone),
):
    return compute_trend(db, patient_id, period_days, tz=tz)


@router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    reading = db.query(BPReading).filter(BPReading.reading_id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading not found")
    if reading.patient_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reading")
    db.delete(reading)
    db.commit()
