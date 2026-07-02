from datetime import datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import AuthToken, get_session
from app.shared.tokens import decode_access_token


async def require_access_token(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"message": "토큰이 제공되지 않았거나 유효하지 않습니다."},
        )
    token = authorization.removeprefix("Bearer ").strip()
    token_user_id = decode_access_token(token)
    if token_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"message": "토큰이 제공되지 않았거나 유효하지 않습니다."},
        )
    auth_token = await session.scalar(select(AuthToken).where(AuthToken.token == token))
    if auth_token is None or auth_token.user_id != token_user_id:
        raise HTTPException(
            status_code=401,
            detail={"message": "토큰이 제공되지 않았거나 유효하지 않습니다."},
        )
    if auth_token.expires_at is not None and auth_token.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=401,
            detail={"message": "토큰이 제공되지 않았거나 유효하지 않습니다."},
        )
    return auth_token.user_id
