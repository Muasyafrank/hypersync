import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.localtime import DEFAULT_TIMEZONE_NAME


class UserRole(str, enum.Enum):
    patient = "patient"
    clinician = "clinician"
    admin = "admin"


class SexEnum(str, enum.Enum):
    male = "Male"
    female = "Female"
    other = "Other"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    role = Column(Enum(UserRole), nullable=True, default=UserRole.patient)

    full_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False)

    password_hash = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    profile = relationship(
        "PatientProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    profile_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)

    date_of_birth = Column(Date, nullable=True)

    sex = Column(Enum(SexEnum), nullable=True)

    # The patient's own calendar is used when a clinician reviews weekly
    # averages. It is captured at registration and does not depend on the
    # clinician's browser timezone.
    timezone = Column(
        String,
        nullable=False,
        default=DEFAULT_TIMEZONE_NAME,
        server_default=DEFAULT_TIMEZONE_NAME,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="profile")
