import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, oauth2_scheme, parse_uuid
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.token import BlacklistedToken, RefreshToken
from app.models.user import PatientProfile, User
from app.schemas.auth import AccessTokenOnly, RefreshRequest
from app.schemas.user import UserOut, UserRegister, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])


# The refresh token lives in an httpOnly cookie so page scripts (and therefore
# any XSS) can never read it. It is scoped to /auth, the only place it is used.
REFRESH_COOKIE = "hs_refresh"
REFRESH_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _clear_refresh_cookie(response: Response) -> None:
    # Attributes must match those used to set it, or the browser keeps the cookie.
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _refresh_token_from(request: Request, body: RefreshRequest | None) -> str | None:
    """The cookie for browsers; the request body for API clients without one."""
    return request.cookies.get(REFRESH_COOKIE) or (body.refresh_token if body else None)


def _as_utc(moment: datetime) -> datetime:
    """Some database drivers return naive datetimes; they are stored as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _start_session(user: User, db: Session, response: Response) -> AccessTokenOnly:
    """Mint a token pair: the access token goes in the body, the refresh token in the cookie."""
    access_token, _, _ = create_access_token(data={"sub": str(user.user_id), "role": user.role.value})
    refresh_token, refresh_jti, refresh_expires = create_refresh_token(data={"sub": str(user.user_id)})

    db.add(
        RefreshToken(
            token_id=uuid.UUID(refresh_jti),
            user_id=user.user_id,
            expires_at=refresh_expires,
        )
    )
    db.commit()

    _set_refresh_cookie(response, refresh_token)
    return AccessTokenOnly(access_token=access_token)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.patient,
    )
    db.add(user)
    db.flush()

    db.add(PatientProfile(user_id=user.user_id, date_of_birth=payload.date_of_birth, sex=payload.sex))

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=AccessTokenOnly)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _start_session(user, db, response)


@router.post("/refresh", response_model=AccessTokenOnly)
def refresh_access_token(request: Request, payload: RefreshRequest | None = None, db: Session = Depends(get_db)):
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    refresh_token = _refresh_token_from(request, payload)
    token_payload = decode_token(refresh_token) if refresh_token else None
    if token_payload is None or token_payload.get("type") != "refresh":
        raise invalid

    jti = parse_uuid(token_payload.get("jti"))
    sub = parse_uuid(token_payload.get("sub"))
    if jti is None or sub is None:
        raise invalid

    stored = db.query(RefreshToken).filter(RefreshToken.token_id == jti).first()
    if not stored or stored.revoked or _as_utc(stored.expires_at) < datetime.now(UTC):
        raise invalid

    user = db.query(User).filter(User.user_id == sub).first()
    if not user:
        raise invalid

    new_access_token, _, _ = create_access_token(data={"sub": str(user.user_id), "role": user.role.value})
    return AccessTokenOnly(access_token=new_access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_payload = decode_token(token) or {}
    access_jti = parse_uuid(access_payload.get("jti"))
    if access_jti:
        db.add(
            BlacklistedToken(
                jti=access_jti,
                expires_at=datetime.fromtimestamp(access_payload["exp"], tz=UTC),
            )
        )

    refresh_token = _refresh_token_from(request, payload)
    refresh_jti = parse_uuid((decode_token(refresh_token) or {}).get("jti")) if refresh_token else None
    if refresh_jti:
        stored = db.query(RefreshToken).filter(RefreshToken.token_id == refresh_jti).first()
        if stored and stored.user_id == current_user.user_id:
            stored.revoked = True

    db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
