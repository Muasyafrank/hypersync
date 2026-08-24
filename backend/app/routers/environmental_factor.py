import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.environmental_factor import EnvironmentalFactor
from app.schemas.environmental_factor import EnvironmentalFactorCreate, EnvironmentalFactorOut

router = APIRouter(prefix="/factors", tags=["Environmental Factors"])


@router.post("/", response_model=EnvironmentalFactorOut, status_code=status.HTTP_201_CREATED)
def log_factor(
    payload: EnvironmentalFactorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can log environmental factors")

    factor = EnvironmentalFactor(
        patient_id=current_user.user_id,
        stress_level=payload.stress_level,
        sleep_hours=payload.sleep_hours,
        diet_adherence=payload.diet_adherence,
        medication_taken=payload.medication_taken,
        logged_date=payload.logged_date or date.today(),
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return factor


@router.get("/me", response_model=List[EnvironmentalFactorOut])
def get_my_factors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can view their own factors")

    return (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id == current_user.user_id)
        .order_by(EnvironmentalFactor.logged_date.desc())
        .all()
    )


@router.get("/patient/{patient_id}", response_model=List[EnvironmentalFactorOut])
def get_patient_factors(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians can view patient factors")

    return (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id == patient_id)
        .order_by(EnvironmentalFactor.logged_date.desc())
        .all()
    )


@router.delete("/{factor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_factor(
    factor_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    factor = db.query(EnvironmentalFactor).filter(EnvironmentalFactor.factor_id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    if factor.patient_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your entry")
    db.delete(factor)
    db.commit()