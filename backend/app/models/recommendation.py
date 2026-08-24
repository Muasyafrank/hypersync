import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(String, nullable=False)
    based_on_trend = Column(String, nullable=True)  # e.g. "elevated", "high"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("User", backref=backref("recommendations", passive_deletes=True))