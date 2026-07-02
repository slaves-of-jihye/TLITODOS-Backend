import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import User, get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/users/me", tags=["authorization"])
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


class DiscordLinkRequest(BaseModel):
    discord_auth_code: str = Field(alias="discordAuthCode", min_length=1)


@router.post("/discord")
async def link_discord(
    payload: DiscordLinkRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    discord_user = await fetch_discord_user(payload.discord_auth_code)
    user = await session.get(User, user_id)
    user.is_discord_linked = True
    user.discord_username = discord_user["username"]
    await session.commit()
    return {
        "success": True,
        "discordUsername": user.discord_username,
    }


async def fetch_discord_user(code: str) -> dict:
    client_id = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail={"message": "Discord OAuth 환경변수가 설정되지 않았습니다."})

    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail={"message": "유효하지 않은 디스코드 인증 코드입니다."})
        access_token = token_response.json().get("access_token")
        user_response = await client.get(DISCORD_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail={"message": "디스코드 사용자 정보를 가져올 수 없습니다."})
        user = user_response.json()
    username = user.get("global_name") or user.get("username")
    if not username:
        raise HTTPException(status_code=400, detail={"message": "디스코드 사용자 이름을 확인할 수 없습니다."})
    return {"username": username}
