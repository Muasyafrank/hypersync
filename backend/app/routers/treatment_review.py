import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_clinician
from app.core.patient_context import patient_timezone
from app.core.treatment_review import assess_patients
from app.models.treatment_review import TreatmentReviewRecord
from app.models.user import User, UserRole
from app.schemas.treatment_review import MarkReviewedIn, ReviewRecordOut, TreatmentReviewOut

router = APIRouter(prefix="/treatment-review", tags=["Treatment review"])

RECENT_REVIEWS_SHOWN = 5


def _patient_or_404(db: Session, patient_id: uuid.UUID) -> User:
    patient = db.query(User).filter(User.user_id == patient_id, User.role == UserRole.patient).first()
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient


def _build(db: Session, patient: User) -> TreatmentReviewOut:
    assessment = assess_patients(
        db,
        [patient.user_id],
        timezones={patient.user_id: patient_timezone(db, patient.user_id)},
    )[patient.user_id]

    rows = (
        db.query(TreatmentReviewRecord, User.full_name)
        .outerjoin(User, User.user_id == TreatmentReviewRecord.clinician_id)
        .filter(TreatmentReviewRecord.patient_id == patient.user_id)
        .order_by(TreatmentReviewRecord.reviewed_at.desc())
        .limit(RECENT_REVIEWS_SHOWN)
        .all()
    )
    out = TreatmentReviewOut.model_validate(assessment)
    out.recent_reviews = [
        ReviewRecordOut(
            review_id=record.review_id,
            reviewed_at=record.reviewed_at,
            clinician_name=record.clinician_name or name,
            note=record.note,
            flag_kind=record.flag_kind,
            flag_level=record.flag_level,
        )
        for record, name in rows
    ]
    return out


@router.get("/patients/{patient_id}", response_model=TreatmentReviewOut)
def get_treatment_review(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Whether this patient is flagged for a treatment review, and why."""
    return _build(db, _patient_or_404(db, patient_id))


@router.post("/patients/{patient_id}/reviewed", response_model=TreatmentReviewOut, status_code=status.HTTP_201_CREATED)
def mark_reviewed(
    patient_id: uuid.UUID,
    payload: MarkReviewedIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Record that the clinician reviewed this patient. Pauses the flag for a while."""
    patient = _patient_or_404(db, patient_id)
    patient_tz = patient_timezone(db, patient.user_id)
    flagged = assess_patients(db, [patient.user_id], timezones={patient.user_id: patient_tz})[patient.user_id]
    db.add(
        TreatmentReviewRecord(
            patient_id=patient.user_id,
            clinician_id=current_user.user_id,
            clinician_name=current_user.full_name,
            reviewed_at=datetime.now(UTC),
            note=payload.note or None,
            flag_kind=flagged.kind,
            flag_level=flagged.level,
        )
    )
    db.commit()
    return _build(db, patient)
