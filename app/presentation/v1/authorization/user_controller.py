from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import auth_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token
from app.shared.fonts import SUPPORTED_FONTS


router = APIRouter(prefix="/api/v1/users/me", tags=["authorization"])


class NotificationSettingsRequest(BaseModel):
    discord_alert_enabled: bool = Field(alias="discordAlertEnabled")


class FontSettingRequest(BaseModel):
    font: str

    @field_validator("font")
    @classmethod
    def known_font(cls, value: str) -> str:
        if value not in SUPPORTED_FONTS:
            raise ValueError("unsupported font")
        return value


@router.get("")
async def get_me(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.get_me(session, user_id)


@router.patch("")
async def update_me(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    updates: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        updates = {key: value for key, value in body.items() if value is not None}
    elif "multipart/form-data" in content_type:
        form = await request.form()
        updates = await auth_service.form_updates(form)
    return await auth_service.update_me(session, user_id, updates)


@router.patch("/notifications")
async def update_notifications(
    payload: NotificationSettingsRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.update_notifications(session, user_id, payload.discord_alert_enabled)


@router.patch("/font")
async def update_font(
    payload: FontSettingRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.update_font(session, user_id, payload.font)
