from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import bets_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/bets", tags=["bets"])


class BetStatusRequest(BaseModel):
    status: Literal["ACCEPTED", "REJECTED"]


class BetVerifyRequest(BaseModel):
    approved: bool = True


@router.patch("/{betId}/status")
async def update_bet_status(
    betId: int,
    payload: BetStatusRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await bets_service.update_bet_status(session, betId, payload, user_id)


@router.post("/{betId}/proof")
async def upload_bet_proof(
    betId: int,
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        return await bets_service.upload_bet_proof(session, betId, form, user_id)
    else:
        raise HTTPException(status_code=400, detail={"message": "multipart/form-data로 이미지 파일을 첨부해야 합니다."})


@router.patch("/{betId}/verify")
async def verify_bet(
    betId: int,
    payload: BetVerifyRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await bets_service.verify_bet(session, betId, payload, user_id)
