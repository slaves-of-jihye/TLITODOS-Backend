from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import auth_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/users/me", tags=["authorization"])


class DiscordLinkRequest(BaseModel):
    discord_auth_code: str = Field(alias="discordAuthCode", min_length=1)


@router.post("/discord")
async def link_discord(
    payload: DiscordLinkRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.link_discord(session, user_id, payload.discord_auth_code)
