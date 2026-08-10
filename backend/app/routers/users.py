from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/",response_model=List[UserOut])
def list_users(
    role:UserRole | None = Query(default=None, description="Filter by role: patient or clinician"),
    db:Session = Depends(get_db),
    current_user: User = Depends(require_role("clinician"))
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).all()