from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt


JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "change-me-in-local-env")


def create_access_token(user_id: int) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")))
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "exp": expires_at,
            "jti": secrets.token_urlsafe(16),
        },
        _jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_at.replace(tzinfo=None)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
