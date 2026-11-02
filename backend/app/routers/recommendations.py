from datetime import UTC, datetime, timedelta, tzinfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_timezone, require_patient
from app.core.ml_recommendation_engine import generate_recommendations_ml
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.recommendation import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

# How long a generated batch stays "fresh". Within this window the stored
# batch is returned as-is instead of writing a duplicate set of rows.
CACHE_WINDOW_HOURS = 12


@router.get("/me", response_model=list[RecommendationOut])
def get_my_recommendations(
    period_days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
    tz: tzinfo = Depends(get_timezone),
):
    """Return the patient's current recommendations.

    Recommendations are regenerated at most once every CACHE_WINDOW_HOURS.
    Previously every dashboard load wrote a fresh batch of rows, so the
    table grew without bound and the history was mostly duplicates.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=CACHE_WINDOW_HOURS)
    cached = (
        db.query(Recommendation)
        .filter(
            Recommendation.patient_id == current_user.user_id,
            Recommendation.created_at >= cutoff,
        )
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    if cached:
        return cached

    generated = generate_recommendations_ml(db, current_user.user_id, period_days, tz=tz)

    saved = [
        Recommendation(
            patient_id=current_user.user_id,
            message=rec["message"],
            based_on_trend=rec.get("based_on_trend"),
            confidence=float(rec["confidence"]) if rec.get("confidence") is not None else None,
            source=rec.get("source"),
        )
        for rec in generated
    ]
    db.add_all(saved)
    db.commit()
    for entry in saved:
        db.refresh(entry)
    return saved
