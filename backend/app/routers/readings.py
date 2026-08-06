import uuid
from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.reading import BPReading
from app.schemas.reading import BPReadingCreate, BPReadingOut
from app.core.bp_classification import classify_bp
from app.core.trend_analysis import compute_trend
from app.schemas.trend import TrendSummary

router = APIRouter(prefix="/readings", tags=["Blood Pressure Readings"])

def _to_out(reading: BPReading) -> BPReadingOut:
    return BPReadingOut(
        reading_id=reading.reading_id,
        patient_id=reading.patient_id,
        systolic=reading.systolic,
        diastolic=reading.diastolic,
        heart_rate=reading.heart_rate,
        recorded_at=reading.recorded_at,
        source=reading.source,
        notes= reading.notes or " ",
        status=classify_bp(reading.systolic, reading.diastolic),
    )

@router.post("/", response_model=BPReadingOut, status_code= status.HTTP_201_CREATED)
def create_reading(
    payload: BPReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can create readings.")
    reading = BPReading(
        patient_id=current_user.user_id,
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        heart_rate=payload.heart_rate,
        recorded_at=payload.recorded_at or None,
        source=payload.source,
        notes= payload.notes
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return _to_out(reading)

@router.get("/me", response_model=List[BPReadingOut])
def get_my_readings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code = status.HTTP_403_FORBIDDEN, detail="Only patients can view their readings.")
    readings = (
        db.query(BPReading).filter(BPReading.patient_id == current_user.user_id).order_by(BPReading.recorded_at.desc()).all()
    )
    return [_to_out(r) for r in readings]

@router.get("/patient/{patient_id}", response_model=List[BPReadingOut])
def get_patient_readings(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Only clinicians can view patient records")

    readings = (
        db.query(BPReading).filter(BPReading.patient_id == patient_id).order_by(BPReading.recorded_at.desc()).all()
    )
    return [_to_out(r) for r in readings]

@router.get("/me/trend", response_model=TrendSummary)
def get_my_trend(
    period_days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can view their own trend")

    return compute_trend(db, current_user.user_id, period_days)


@router.get("/patient/{patient_id}/trend", response_model=TrendSummary)
def get_patient_trend(
    patient_id: uuid.UUID,
    period_days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians can view patient trends")

    return compute_trend(db, patient_id, period_days)

@router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id:uuid.UUID,
    db:Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
   reading = db.query(BPReading).filter(BPReading.reading_id == reading_id).first()
   if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading not found")
   if reading.patient_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reading")
   db.delete(reading)
   db.commit() 
