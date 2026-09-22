import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.bp_classification import classify_bp
from app.core.database import get_db
from app.core.deps import require_admin, require_clinician, require_staff
from app.core.security import hash_password
from app.models.reading import BPReading
from app.models.user import PatientProfile, User, UserRole
from app.schemas.user import (
    ClinicianCreate,
    LatestReading,
    PasswordReset,
    PatientSummaryOut,
    UserDetailOut,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=List[UserOut])
def list_users(
    role: UserRole | None = Query(default=None, description="Filter by role: patient, clinician or admin"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    query = db.query(User)

    if current_user.role == UserRole.clinician:
        # Clinicians only ever see patients, whatever filter they pass.
        query = query.filter(User.role == UserRole.patient)
    elif role:
        query = query.filter(User.role == role)

    return query.order_by(User.created_at.desc()).all()


@router.get("/patients/summary", response_model=List[PatientSummaryOut])
def list_patient_summaries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Patient list with each patient's latest reading and total count.

    Replaces the previous approach of fetching every patient's full reading
    history from the client, which was one request per patient plus the
    entire history transferred just to read the first row.
    """
    patients = (
        db.query(User)
        .filter(User.role == UserRole.patient)
        .order_by(User.created_at.desc())
        .all()
    )
    if not patients:
        return []

    patient_ids = [p.user_id for p in patients]

    counts = dict(
        db.query(BPReading.patient_id, func.count(BPReading.reading_id))
        .filter(BPReading.patient_id.in_(patient_ids))
        .group_by(BPReading.patient_id)
        .all()
    )

    # One row per patient: their most recent reading.
    latest_rows = (
        db.query(BPReading)
        .filter(BPReading.patient_id.in_(patient_ids))
        .distinct(BPReading.patient_id)
        .order_by(BPReading.patient_id, BPReading.recorded_at.desc())
        .all()
    )
    latest_by_patient = {row.patient_id: row for row in latest_rows}

    summaries = []
    for patient in patients:
        reading = latest_by_patient.get(patient.user_id)
        summaries.append(
            PatientSummaryOut(
                user_id=patient.user_id,
                full_name=patient.full_name,
                email=patient.email,
                reading_count=counts.get(patient.user_id, 0),
                latest=LatestReading(
                    systolic=reading.systolic,
                    diastolic=reading.diastolic,
                    status=classify_bp(reading.systolic, reading.diastolic),
                    recorded_at=reading.recorded_at,
                )
                if reading
                else None,
            )
        )
    return summaries


@router.post("/clinicians", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_clinician(
    payload: ClinicianCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if db.query(User.user_id).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    clinician = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.clinician,
    )
    db.add(clinician)
    db.commit()
    db.refresh(clinician)
    return clinician


@router.get("/{user_id}", response_model=UserDetailOut)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    user = _get_user_or_404(db, user_id)

    if current_user.role == UserRole.clinician and user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user")

    detail = UserDetailOut.model_validate(user, from_attributes=True)

    if user.role == UserRole.patient:
        profile = db.query(PatientProfile).filter(PatientProfile.user_id == user.user_id).first()
        if profile:
            detail.date_of_birth = profile.date_of_birth
            detail.sex = profile.sex
        detail.reading_count = (
            db.query(func.count(BPReading.reading_id))
            .filter(BPReading.patient_id == user.user_id)
            .scalar()
        )
    return detail


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)

    if payload.email and payload.email != user.email:
        if db.query(User.user_id).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        user.email = payload.email

    if payload.full_name:
        user.full_name = payload.full_name

    if payload.role and payload.role != user.role:
        if user.user_id == current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role",
            )
        user.role = payload.role

    if payload.password:
        user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    user = _get_user_or_404(db, user_id)
    db.delete(user)
    db.commit()
