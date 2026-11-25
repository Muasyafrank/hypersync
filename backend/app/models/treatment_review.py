import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class TreatmentReviewRecord(Base):
    """A clinician's note that they reviewed a patient's treatment.

    It pauses the treatment-review flag for a while (see app/core/treatment_review.py)
    and gives a dated trail of who reviewed what. It records that a review took
    place, not what was decided: prescribing belongs in the clinic's own records.
    """

    __tablename__ = "treatment_reviews"

    review_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    clinician_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    # Snapshot the reviewer name so deleting or renaming the account does not
    # erase who performed the historical review.
    clinician_name = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    note = Column(String, nullable=True)
    # What the flag said at the time ("sustained_elevated_high" / "sustained_low"), if it was raised.
    flag_kind = Column(String, nullable=True)
    # Severity at review time. A later escalation must not be hidden by an
    # earlier routine-level review.
    flag_level = Column(String, nullable=True)
