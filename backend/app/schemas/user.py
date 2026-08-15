import uuid
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole,SexEnum

class UserRegister(BaseModel):
    full_name: str 
    email: EmailStr
    password: str = Field(min_length = 8)
    # role: UserRole
    date_of_birth: date | None = None
    sex: SexEnum  | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password : str

class UserOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class ClinicianCreate(BaseModel):
    full_name:str
    email: EmailStr
    password: str = Field(min_length=8)
        