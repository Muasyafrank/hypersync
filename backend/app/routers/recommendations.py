import uuid
from datetime import UTC, datetime, tzinfo

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_timezone, require_patient
from app.core.ml_recommendation_engine import generate_recommendations_ml
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.recommendation import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

# The period the patient's standing advice is based on. Other periods are answered
# but not stored, so flicking between 7 and 30 days doesn't churn the history.
DEFAULT_PERIOD_DAYS = 7

# Past batches are kept as a record of what the patient was told and when. Only
# the newest MAX_HISTORY_BATCHES are kept per patient.
MAX_HISTORY_BATCHES = 30


def _signature(items) -> list[tuple]:
    """What makes two batches 'the same advice' (works for stored rows and freshly generated dicts)."""

    def field(item, name):
        return item[name] if isinstance(item, dict) else getattr(item, name)

    return [
        (field(i, "message"), field(i, "based_on_trend"), field(i, "source"), field(i, "confidence")) for i in items
    ]


def _latest_batch(db: Session, patient_id) -> list[Recommendation]:
    newest = db.query(func.max(Recommendation.created_at)).filter(Recommendation.patient_id == patient_id).scalar()
    if newest is None:
        return []
    return (
        db.query(Recommendation)
        .filter(Recommendation.patient_id == patient_id, Recommendation.created_at == newest)
        .order_by(Recommendation.position)
        .all()
    )


def _prune(db: Session, patient_id) -> None:
    """Drop batches older than the newest MAX_HISTORY_BATCHES."""
    boundary = (
        db.query(Recommendation.created_at)
        .filter(Recommendation.patient_id == patient_id)
        .group_by(Recommendation.created_at)
        .order_by(Recommendation.created_at.desc())
        .offset(MAX_HISTORY_BATCHES)
        .limit(1)
        .scalar()
    )
    if boundary is not None:
        db.query(Recommendation).filter(
            Recommendation.patient_id == patient_id, Recommendation.created_at <= boundary
        ).delete(synchronize_session=False)


def _as_row(patient_id, rec: dict, position: int, created_at: datetime) -> Recommendation:
    return Recommendation(
        patient_id=patient_id,
        message=rec["message"],
        based_on_trend=rec.get("based_on_trend"),
        confidence=float(rec["confidence"]) if rec.get("confidence") is not None else None,
        source=rec.get("source"),
        position=position,
        created_at=created_at,
    )


@router.get("/me", response_model=list[RecommendationOut])
def get_my_recommendations(
    response: Response,
    period_days: int = Query(default=DEFAULT_PERIOD_DAYS, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
    tz: tzinfo = Depends(get_timezone),
):
    """The patient's recommendations, worked out from their data as it is right now.

    Nothing is served from a cache, so a reading or lifestyle entry saved a moment
    ago is already reflected. (This used to be reused for 12 hours, so new data
    changed nothing until the next day.)

    For the standing 7-day view a new batch is stored only when the advice has
    actually changed, which keeps a dated record of what the patient was told
    without writing duplicates on every page load.
    """
    response.headers["Cache-Control"] = "no-store"  # also keep browsers and proxies from reusing it

    generated = generate_recommendations_ml(db, current_user.user_id, period_days, tz=tz)
    now = datetime.now(UTC)

    if period_days != DEFAULT_PERIOD_DAYS:
        return [
            RecommendationOut(
                recommendation_id=uuid.uuid4(),
                message=rec["message"],
                based_on_trend=rec.get("based_on_trend"),
                confidence=rec.get("confidence"),
                source=rec.get("source"),
                created_at=now,
            )
            for rec in generated
        ]

    current = _latest_batch(db, current_user.user_id)
    if current and _signature(current) == _signature(generated):
        return current  # unchanged: keep the same rows (and ids) as before

    saved = [_as_row(current_user.user_id, rec, position, now) for position, rec in enumerate(generated)]
    db.add_all(saved)
    db.flush()
    _prune(db, current_user.user_id)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved
