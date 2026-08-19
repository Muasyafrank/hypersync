import uuid
from sqlalchemy import Column, Integer, String,DateTime,ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base

class BPReading(Base):
    __tablename__ = "bp_readings"

    reading_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    systolic = Column(Integer, nullable=False)
    diastolic = Column(Integer, nullable=False)
    heart_rate = Column(Integer, nullable = False)
    recorded_at = Column(DateTime(timezone = True), nullable=False,server_default=func.now())
    source = Column(String,nullable=False,default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String, nullable=True)

    patient = relationship("User", backref=backref("bp_readings", passive_deletes=True))
