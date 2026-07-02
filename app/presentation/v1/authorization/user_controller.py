from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import User, get_session, user_to_response
from app.shared.auth import require_access_token
from app.shared.uploads import save_upload


router = APIRouter(prefix="/api/v1/users/me", tags=["authorization"])


class NotificationSettingsRequest(BaseModel):
    discord_alert_enabled: bool = Field(alias="discordAlertEnabled")


@router.get("")
async def get_me(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    return user_to_response(user)


@router.patch("")
async def update_me(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    updates: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        updates = {key: value for key, value in body.items() if value is not None}
    elif "multipart/form-data" in content_type:
        form = await request.form()
        updates = {key: str(value) for key, value in form.items() if key != "image"}
        image = form.get("image")
        if isinstance(image, UploadFile):
            updates["profileImageUrl"] = await save_upload(image, "profiles")

    if "name" in updates:
        user.name = updates["name"]
    if "bio" in updates:
        user.bio = updates["bio"]
    if "profileImageUrl" in updates:
        user.profile_image_url = updates["profileImageUrl"]
    await session.commit()
    await session.refresh(user)

    return {
        "userId": user.id,
        "name": user.name,
        "profileImageUrl": user.profile_image_url,
        "bio": user.bio,
    }


@router.patch("/notifications")
async def update_notifications(
    payload: NotificationSettingsRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    user.discord_alert_enabled = payload.discord_alert_enabled
    await session.commit()
    return {
        "success": True,
        "discordAlertEnabled": user.discord_alert_enabled,
    }
