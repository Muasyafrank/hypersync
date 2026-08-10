import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user, oauth2_scheme
from app.models.user import User, PatientProfile
from app.models.token import RefreshToken, BlacklistedToken
from app.schemas.user import UserRegister, UserOut
from app.schemas.auth import TokenPair, AccessTokenOnly, RefreshRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _issue_token_pair(user: User, db: Session) -> TokenPair:
    access_token, _, _ = create_access_token(data={"sub": str(user.user_id), "role": user.role.value})
    refresh_token, refresh_jti, refresh_expires = create_refresh_token(data={"sub": str(user.user_id)})

    db.add(RefreshToken(
        token_id=uuid.UUID(refresh_jti),
        user_id=user.user_id,
        expires_at=refresh_expires,
    ))
    db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()

    if payload.role == "patient":
        db.add(PatientProfile(user_id=user.user_id, date_of_birth=payload.date_of_birth, sex=payload.sex))

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token_pair(user, db)


@router.post("/refresh", response_model=AccessTokenOnly)
def refresh_access_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token_payload = decode_token(payload.refresh_token)
    if token_payload is None or token_payload.get("type") != "refresh":
        raise invalid

    jti = token_payload.get("jti")
    sub = token_payload.get("sub")
    if not jti or not sub:
        raise invalid

    stored = db.query(RefreshToken).filter(RefreshToken.token_id == uuid.UUID(jti)).first()
    if not stored or stored.revoked or stored.expires_at < datetime.now(timezone.utc):
        raise invalid

    user = db.query(User).filter(User.user_id == uuid.UUID(sub)).first()
    if not user:
        raise invalid

    new_access_token, _, _ = create_access_token(data={"sub": str(user.user_id), "role": user.role.value})
    return AccessTokenOnly(access_token=new_access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_payload = decode_token(token)
    if access_payload and access_payload.get("jti"):
        db.add(BlacklistedToken(
            jti=uuid.UUID(access_payload["jti"]),
            expires_at=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc),
        ))

    refresh_payload = decode_token(payload.refresh_token)
    if refresh_payload and refresh_payload.get("jti"):
        stored = db.query(RefreshToken).filter(RefreshToken.token_id == uuid.UUID(refresh_payload["jti"])).first()
        if stored and stored.user_id == current_user.user_id:
            stored.revoked = True

    db.commit()


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user