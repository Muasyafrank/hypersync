import uuid
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError
from app.core.config import settings

pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def _create_token(data:dict,expires_delta:timedelta,token_type: str) -> tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {**data, "exp":expire,"jti":jti,"type":token_type}
    token = jwt.encode(to_encode,settings.secret_key,algorithm=settings.algorithm)
    return token, jti, expire

def create_access_token(data:dict) -> tuple[str,str,datetime]:
    return _create_token(data,timedelta(minutes=settings.access_token_expire_minutes),"access")

def create_refresh_token(data:dict) -> tuple[str,str,datetime]:
    return _create_token(data,timedelta(days=settings.refresh_token_expire_days),"refresh")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token,settings.secret_key, algorithms = [settings.algorithm])
    except JWTError:
        return None