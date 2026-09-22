import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.token import BlacklistedToken
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a UUID from an untrusted token claim without raising."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload is None:
        raise CREDENTIALS_ERROR

    user_id = _parse_uuid(payload.get("sub"))
    if user_id is None:
        raise CREDENTIALS_ERROR

    jti = _parse_uuid(payload.get("jti"))
    if jti and db.query(BlacklistedToken.jti).filter(BlacklistedToken.jti == jti).first():
        raise CREDENTIALS_ERROR

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise CREDENTIALS_ERROR
    return user


def require_role(*allowed_roles: str):
    """Dependency factory: allow only the given roles through.

    Use this instead of hand-rolled ``if current_user.role != "patient"``
    checks inside route bodies, so the rule is declared in the signature
    and shows up in the generated OpenAPI docs.
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_checker


require_patient = require_role("patient")
require_clinician = require_role("clinician")
require_admin = require_role("admin")
require_staff = require_role("clinician", "admin")
