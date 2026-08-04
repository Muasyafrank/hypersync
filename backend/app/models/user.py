import uuid
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str,enum.Enum):
    patient = "patient"
    clinician = "clinician"

class SexEnum(str, enum.Enum):
    male = "Male"
    female = "Female"
    other = "Other"

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True),primary_key=True, default = uuid.uuid4)
    role = Column(Enum(UserRole), nullable = False)
    full_name = Column(String, nullable = False)
    email = Column(String, unique = True, nullable = False)
    password_hash = Column(String, nullable = False)
    created_at = Column(DateTime(timezone = True), server_default = func.now())

    profile = relationship("PatientProfile", back_populates="user", uselist = False)

class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    profile_id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    user_id = Column(UUID(as_uuid= True),ForeignKey("users.user_id"),nullable = False)
    date_of_birth = Column(Date, nullable = True)
    sex = Column(Enum(SexEnum), nullable = True) 
    created_at = Column(DateTime(timezone = True), server_default = func.now())

    user = relationship("User", back_populates = "profile")   