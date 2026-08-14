from datetime import datetime, timedelta

from jose import jwt, JWTError

from app.core.config import settings


def create_reset_token(employee_code: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.RESET_EXPIRE_MINUTES)
    payload = {"sub": employee_code, "exp": expire, "type": "password_reset"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except JWTError:
        return None
