import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import AuthToken, User, ensure_user_defaults, get_session
from app.shared.tokens import create_access_token


router = APIRouter(prefix="/api/v1/auth", tags=["authorization"])
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleLoginRequest(BaseModel):
    google_access_token: str = Field(alias="googleAccessToken", min_length=1)


@router.post("/google")
async def login_with_google(
    payload: GoogleLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    google_profile = await fetch_google_profile(payload.google_access_token)
    user = await upsert_google_user(session, google_profile)
    access_token, expires_at = create_access_token(user.id)
    session.add(AuthToken(token=access_token, user_id=user.id, expires_at=expires_at))
    await session.commit()
    return {
        "accessToken": access_token,
        "expiresAt": expires_at.isoformat(),
        "isNewUser": google_profile["isNewUser"],
    }


async def fetch_google_profile(access_token: str) -> dict:
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not google_client_id:
        raise HTTPException(status_code=500, detail={"message": "GOOGLE_CLIENT_ID가 설정되지 않았습니다."})

    async with httpx.AsyncClient(timeout=10) as client:
        tokeninfo_response = await client.get(GOOGLE_TOKENINFO_URL, params={"access_token": access_token})
        if tokeninfo_response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail={"message": "유효하지 않거나 만료된 구글 토큰입니다."},
            )
        tokeninfo = tokeninfo_response.json()
        audience = tokeninfo.get("audience") or tokeninfo.get("aud") or tokeninfo.get("issued_to")
        if audience != google_client_id:
            raise HTTPException(
                status_code=401,
                detail={"message": "구글 토큰의 클라이언트 ID가 일치하지 않습니다."},
            )

        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail={"message": "구글 사용자 정보를 가져올 수 없습니다."},
            )
        userinfo = userinfo_response.json()

    google_sub = userinfo.get("sub") or tokeninfo.get("user_id")
    if not google_sub:
        raise HTTPException(
            status_code=401,
            detail={"message": "구글 사용자 식별자를 확인할 수 없습니다."},
        )

    return {
        "googleSub": google_sub,
        "email": userinfo.get("email") or tokeninfo.get("email"),
        "name": userinfo.get("name") or userinfo.get("email") or "TLITODOS User",
        "picture": userinfo.get("picture"),
        "isNewUser": False,
    }


async def upsert_google_user(session: AsyncSession, profile: dict) -> User:
    user = await session.scalar(select(User).where(User.google_sub == profile["googleSub"]))
    if user is None and profile.get("email"):
        user = await session.scalar(select(User).where(User.email == profile["email"]))
    if user is None:
        user = User(
            google_sub=profile["googleSub"],
            email=profile.get("email"),
            name=profile["name"],
            profile_image_url=profile.get("picture"),
            bio="",
        )
        session.add(user)
        await session.flush()
        await ensure_user_defaults(session, user.id)
        profile["isNewUser"] = True
    else:
        user.google_sub = profile["googleSub"]
        user.email = profile.get("email") or user.email
        user.name = profile["name"] or user.name
        user.profile_image_url = profile.get("picture") or user.profile_image_url
    return user
