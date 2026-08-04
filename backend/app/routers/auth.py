from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token,hash_password
from app.core.deps import get_current_user
from app.models.user import User, PatientProfile
from app.schemas.auth import Token
from app.schemas.user import UserRegister, UserLogin, UserOut

router = APIRouter(prefix = "/auth", tags = ["Authentication"])
@router.post("/register", response_model = UserOut, status_code = status.HTTP_201_CREATED)
def register(payload:UserRegister,db:Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail = " Email already registered")

    user = User(
        full_name = payload.full_name,
        email = payload.email,
        password_hash = hash_password(payload.password),
        role = payload.role
    )
    db.add(user)
    db.flush()


    if payload.role == "patient":
        profile = PatientProfile(
            user_id = user.user_id,
            date_of_birth = payload.date_of_birth,
            sex = payload.sex
        )
        db.add(profile)

    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model = Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db:Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED,
                            detail = "Incorrect email or password",
                            headers = {"WWW-Authenticate": "Bearer"}
                            )
    access_token = create_access_token(data = {"sub": str(user.user_id), "role": user.role.value})
    return  Token(access_token = access_token, token_type = "bearer")

@router.get("/me", response_model = UserOut)
def read_current_user(current_user:User = Depends(get_current_user)):
    return current_user