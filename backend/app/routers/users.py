from fastapi import APIRouter,Depends,Query, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.core.deps import require_role,get_current_user
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserOut, ClinicianCreate

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/",response_model=List[UserOut])
def list_users(
    role:UserRole | None = Query(default=None, description="Filter by role: patient or clinician"),
    db:Session = Depends(get_db),
    current_user: User = Depends(require_role("clinician"))
):
    query = db.query(User)
    if current_user.role == UserRole.clinician:
        query = query.filter(User.role == UserRole.patient)
    elif role:
        query = query.filter(User.role == role)

    return query.order_by(User.created_at.desc()).all()
@router.post("/clinicians", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_clinician(
    payload: ClinicianCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if user_id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()