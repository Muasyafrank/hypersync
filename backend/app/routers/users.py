from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.core.deps import require_role
from app.core.security import hash_password
from app.models.user import User, UserRole, PatientProfile
from app.schemas.user import UserOut, ClinicianCreate,UserUpdate,PasswordReset,UserDetailOut
from app.models.reading import BPReading

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[UserOut])
def list_users(
    role: UserRole | None = Query(
        default=None,
        description="Filter by role: patient or clinician"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role("admin", "clinician")
    ),
):
    query = db.query(User)

    # Clinicians can only see patients
    if current_user.role == UserRole.clinician:
        query = query.filter(User.role == UserRole.patient)

    # Admins can filter users by role or see everyone
    elif role:
        query = query.filter(User.role == role)

    return query.order_by(User.created_at.desc()).all()


@router.post(
    "/clinicians",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
def create_clinician(
    payload: ClinicianCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    existing = db.query(User).filter(
        User.email == payload.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

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
    user_id:uuid.UUID,
    db:Session = Depends(get_db),
    current_user:User = Depends(require_role("clinician","admin")),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == UserRole.clinician and user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user")

    detail = UserDetailOut.model_validate(user,from_attributes=True)

    if user.role == UserRole.patient:
        profile = db.query(PatientProfile).filter(PatientProfile.user_id == user.user_id).first()

        if  profile:
            detail.date_of_birth = profile.date_of_birth
            detail.sex = profile.sex
        detail.reading_count = db.query(BPReading).filter(BPReading.patient_id == user.user_id).count()
    return detail

    # return user

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload:UserUpdate,
    db:Session = Depends(get_db),
    current_user:User = Depends(require_role("admin"))

):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not Found")

    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Email already in use")
        user.email = payload.email

    if payload.full_name:
        user.full_name = payload.full_name

    if payload.role:
        if user.user_id == current_user.user_id and payload.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Cannot change your own role")
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
    current_user: User = Depends(require_role("admin")),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    db.commit()


    
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()