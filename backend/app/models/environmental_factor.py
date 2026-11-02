import enum
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class StressLevel(str, enum.Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class IntakeLevel(str, enum.Enum):
    none = "none"
    low = "low"
    moderate = "moderate"
    high = "high"


class EnvironmentalFactor(Base):
    __tablename__ = "environmental_factors"

    factor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    stress_level = Column(Enum(StressLevel, name="stresslevel"), nullable=True)
    sleep_hours = Column(Float, nullable=True)
    diet_adherence = Column(Boolean, nullable=True)
    medication_taken = Column(Boolean, nullable=True)
    salt_intake = Column(Enum(IntakeLevel, name="intakelevel"), nullable=True)
    caffeine_intake = Column(Enum(IntakeLevel, name="intakelevel"), nullable=True)
    alcohol_consumed = Column(Boolean, nullable=True)
    smoked = Column(Boolean, nullable=True)
    physical_activity_minutes = Column(Integer, nullable=True)
    logged_date = Column(Date, nullable=False, server_default=func.current_date())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("User", backref=backref("environmental_factors", passive_deletes=True))
