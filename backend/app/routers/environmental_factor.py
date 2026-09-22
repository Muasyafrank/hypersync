import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_clinician, require_patient
from app.models.environmental_factor import EnvironmentalFactor
from app.models.user import User
from app.schemas.environmental_factor import EnvironmentalFactorCreate, EnvironmentalFactorOut

router = APIRouter(prefix="/factors", tags=["Environmental Factors"])

FACTOR_FIELDS = (
    "stress_level",
    "sleep_hours",
    "diet_adherence",
    "medication_taken",
    "salt_intake",
    "caffeine_intake",
    "alcohol_consumed",
    "smoked",
    "physical_activity_minutes",
)


def _factors_for(db: Session, patient_id) -> list[EnvironmentalFactor]:
    return (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id == patient_id)
        .order_by(EnvironmentalFactor.logged_date.desc())
        .all()
    )


@router.post("", response_model=EnvironmentalFactorOut, status_code=status.HTTP_201_CREATED)
def log_factor(
    payload: EnvironmentalFactorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    factor = EnvironmentalFactor(
        patient_id=current_user.user_id,
        logged_date=payload.logged_date or date.today(),
        **{field: getattr(payload, field) for field in FACTOR_FIELDS},
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return factor


@router.get("/me", response_model=List[EnvironmentalFactorOut])
def get_my_factors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    return _factors_for(db, current_user.user_id)


@router.get("/patient/{patient_id}", response_model=List[EnvironmentalFactorOut])
def get_patient_factors(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    return _factors_for(db, patient_id)


@router.delete("/{factor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_factor(
    factor_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    factor = db.query(EnvironmentalFactor).filter(EnvironmentalFactor.factor_id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    if factor.patient_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your entry")
    db.delete(factor)
    db.commit()
