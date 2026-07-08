import os

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import AuthToken, User, ensure_user_defaults, user_to_response
from app.shared.tokens import create_access_token
from app.shared.uploads import save_upload

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


async def login_with_google(session: AsyncSession, google_access_token: str) -> dict:
    google_profile = await fetch_google_profile(google_access_token)
    user = await upsert_google_user(session, google_profile)
    access_token, expires_at = create_access_token(user.id)
    session.add(AuthToken(token=access_token, user_id=user.id, expires_at=expires_at))
    await session.commit()
    return {"accessToken": access_token, "expiresAt": expires_at.isoformat(), "isNewUser": google_profile["isNewUser"]}


async def fetch_google_profile(access_token: str) -> dict:
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not google_client_id:
        raise HTTPException(status_code=500, detail={"message": "GOOGLE_CLIENT_ID가 설정되지 않았습니다."})

    async with httpx.AsyncClient(timeout=10) as client:
        tokeninfo_response = await client.get(GOOGLE_TOKENINFO_URL, params={"access_token": access_token})
        if tokeninfo_response.status_code != 200:
            raise HTTPException(status_code=401, detail={"message": "유효하지 않거나 만료된 구글 토큰입니다."})
        tokeninfo = tokeninfo_response.json()
        audience = tokeninfo.get("audience") or tokeninfo.get("aud") or tokeninfo.get("issued_to")
        if audience != google_client_id:
            raise HTTPException(status_code=401, detail={"message": "구글 토큰의 클라이언트 ID가 일치하지 않습니다."})

        userinfo_response = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=401, detail={"message": "구글 사용자 정보를 가져올 수 없습니다."})
        userinfo = userinfo_response.json()

    google_sub = userinfo.get("sub") or tokeninfo.get("user_id")
    if not google_sub:
        raise HTTPException(status_code=401, detail={"message": "구글 사용자 식별자를 확인할 수 없습니다."})

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


async def get_me(session: AsyncSession, user_id: int) -> dict:
    return user_to_response(await session.get(User, user_id))


async def update_me(session: AsyncSession, user_id: int, updates: dict) -> dict:
    user = await session.get(User, user_id)
    if "name" in updates:
        user.name = updates["name"]
    if "bio" in updates:
        user.bio = updates["bio"]
    if "profileImageUrl" in updates:
        user.profile_image_url = updates["profileImageUrl"]
    await session.commit()
    await session.refresh(user)
    return {"userId": user.id, "name": user.name, "profileImageUrl": user.profile_image_url, "bio": user.bio}


async def update_notifications(session: AsyncSession, user_id: int, discord_alert_enabled: bool) -> dict:
    user = await session.get(User, user_id)
    user.discord_alert_enabled = discord_alert_enabled
    await session.commit()
    return {"success": True, "discordAlertEnabled": user.discord_alert_enabled}


async def link_discord(session: AsyncSession, user_id: int, discord_auth_code: str) -> dict:
    discord_user = await fetch_discord_user(discord_auth_code)
    user = await session.get(User, user_id)
    user.is_discord_linked = True
    user.discord_username = discord_user["username"]
    await session.commit()
    return {"success": True, "discordUsername": user.discord_username}


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


async def form_updates(form) -> dict:
    from starlette.datastructures import UploadFile

    updates = {key: str(value) for key, value in form.items() if key != "image"}
    image = form.get("image")
    if isinstance(image, UploadFile):
        updates["profileImageUrl"] = await save_upload(image, "profiles")
    return updates
