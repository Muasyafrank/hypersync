from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.recommendation_engine import generate_recommendations
from app.models.user import User
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/me", response_model=List[RecommendationOut])
def get_my_recommendations(
    period_days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can view their own recommendations")

    generated = generate_recommendations(db, current_user.user_id, period_days)

    # persist this batch for history, then return it
    saved = []
    for rec in generated:
        entry = Recommendation(
            patient_id=current_user.user_id,
            message=rec["message"],
            based_on_trend=rec["based_on_trend"],
        )
        db.add(entry)
        saved.append(entry)
    db.commit()
    for entry in saved:
        db.refresh(entry)

    return saved