from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import auth_service
from app.infrastructure.database import get_session


router = APIRouter(prefix="/api/v1/auth", tags=["authorization"])


class GoogleLoginRequest(BaseModel):
    google_access_token: str = Field(alias="googleAccessToken", min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=1)


@router.post("/google")
async def login_with_google(
    payload: GoogleLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.login_with_google(session, payload.google_access_token)


@router.post("/refresh")
async def refresh_tokens(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.refresh_tokens(session, payload.refresh_token)


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.logout(session, payload.refresh_token)
