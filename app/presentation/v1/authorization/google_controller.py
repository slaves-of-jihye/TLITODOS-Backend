from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import auth_service
from app.infrastructure.database import get_session


router = APIRouter(prefix="/api/v1/auth", tags=["authorization"])


class GoogleLoginRequest(BaseModel):
    google_access_token: str = Field(alias="googleAccessToken", min_length=1)


@router.post("/google")
async def login_with_google(
    payload: GoogleLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.login_with_google(session, payload.google_access_token)
