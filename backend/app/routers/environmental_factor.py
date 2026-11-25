import uuid
from datetime import UTC, datetime, tzinfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_timezone, require_clinician, require_patient
from app.core.localtime import local_day
from app.models.environmental_factor import EnvironmentalFactor
from app.models.user import User
from app.schemas.environmental_factor import EnvironmentalFactorCreate, EnvironmentalFactorOut

router = APIRouter(prefix="/factors", tags=["Environmental Factors"])

FACTOR_FIELDS = (
    "stress_level",
    "sleep_hours",
    "diet_adherence",
    "medication_prescribed",
    "medication_taken",
    "salt_intake",
    "caffeine_intake",
    "alcohol_consumed",
    "smoked",
    "physical_activity_minutes",
    "temperature_feel",
    "noise_level",
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
    tz: tzinfo = Depends(get_timezone),
):
    """Save one daily lifestyle/environmental check-in.

    The date is the patient's own calendar day (from ``X-Timezone``). A future
    date is rejected, and there can be only one check-in per patient per day.
    That rule keeps medication adherence and habit patterns meaningful: five
    clicks on one date are one day, not five days.
    """
    today = local_day(datetime.now(UTC), tz)
    logged_date = payload.logged_date or today
    if logged_date > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Lifestyle check-in date cannot be in the future (your current date is {today.isoformat()})",
        )

    existing = (
        db.query(EnvironmentalFactor)
        .filter(
            EnvironmentalFactor.patient_id == current_user.user_id,
            EnvironmentalFactor.logged_date == logged_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lifestyle check-in for {logged_date.isoformat()} already exists",
        )

    factor = EnvironmentalFactor(
        patient_id=current_user.user_id,
        logged_date=logged_date,
        **{field: getattr(payload, field) for field in FACTOR_FIELDS},
    )
    db.add(factor)
    try:
        db.commit()
    except IntegrityError:
        # The database's unique constraint also protects against two requests
        # for the same day arriving at exactly the same time.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lifestyle check-in for {logged_date.isoformat()} already exists",
        ) from None
    db.refresh(factor)
    return factor


@router.get("/me", response_model=list[EnvironmentalFactorOut])
def get_my_factors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    return _factors_for(db, current_user.user_id)


@router.get("/patient/{patient_id}", response_model=list[EnvironmentalFactorOut])
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
