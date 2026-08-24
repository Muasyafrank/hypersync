import uuid
import enum
from sqlalchemy import Column, Integer, Float, Boolean, Date, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base


class StressLevel(str, enum.Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class EnvironmentalFactor(Base):
    __tablename__ = "environmental_factors"

    factor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    stress_level = Column(Enum(StressLevel), nullable=True)
    sleep_hours = Column(Float, nullable=True)
    diet_adherence = Column(Boolean, nullable=True)
    medication_taken = Column(Boolean, nullable=True)
    logged_date = Column(Date, nullable=False, server_default=func.current_date())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("User", backref=backref("environmental_factors", passive_deletes=True))