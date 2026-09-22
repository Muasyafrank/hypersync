import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.alert_engine import maybe_create_alert
from app.core.bp_classification import classify_bp
from app.core.database import get_db
from app.core.deps import require_clinician, require_patient
from app.core.trend_analysis import compute_trend
from app.models.reading import BPReading
from app.models.user import User
from app.schemas.reading import BPReadingCreate, BPReadingOut
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
        status=classify_bp(reading.systolic, reading.diastolic),
    )


def _readings_for(db: Session, patient_id, limit: int | None = None) -> list[BPReading]:
    query = (
        db.query(BPReading)
        .filter(BPReading.patient_id == patient_id)
        .order_by(BPReading.recorded_at.desc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


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


@router.get("/me", response_model=List[BPReadingOut])
def get_my_readings(
    limit: int | None = Query(default=None, ge=1, le=500, description="Most recent N readings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    return [_to_out(r) for r in _readings_for(db, current_user.user_id, limit)]


@router.get("/me/trend", response_model=TrendSummary)
def get_my_trend(
    period_days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    return compute_trend(db, current_user.user_id, period_days)


@router.get("/patient/{patient_id}", response_model=List[BPReadingOut])
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
):
    return compute_trend(db, patient_id, period_days)


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
