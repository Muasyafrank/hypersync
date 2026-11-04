import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class BPReading(Base):
    __tablename__ = "bp_readings"

    reading_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    systolic = Column(Integer, nullable=False)
    diastolic = Column(Integer, nullable=False)
    # Optional: the API schema and the "Log reading" form both treat pulse as
    # optional, so the column must accept NULL (see migration d4e8a1b6f203).
    heart_rate = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String, nullable=True)
    # How the reading was taken. Resting first, and no caffeine, smoking or
    # exercise in the 30 minutes before, are standard conditions for a valid
    # reading. None = the patient did not say.
    rested_before = Column(Boolean, nullable=True)
    stimulant_before = Column(Boolean, nullable=True)

    patient = relationship("User", backref=backref("bp_readings", passive_deletes=True))
