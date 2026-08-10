import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.token import BlacklistedToken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Could not validate credentials",
        headers = {"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception
    jti = payload.get("jti")
    if jti and db.query(BlacklistedToken).filter(BlacklistedToken.jti == uuid.UUID(jti)).first():
        raise credentials_exception

    user = db.query(User).filter(User.user_id == uuid.UUID(payload["sub"])).first()
    if user is None:
        raise credentials_exception
    return user

    # user = db.query(User).filter(User.user_id == payload["sub"]).first()
    # if user is None:
    #     raise credentials_exception
    # return user

def require_role(*allowed_roles: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return current_user
    return role_checker
