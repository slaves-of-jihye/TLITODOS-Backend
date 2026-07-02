from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import Bet, Todo, bet_to_response, get_session
from app.shared.auth import require_access_token
from app.shared.uploads import save_upload


router = APIRouter(prefix="/api/v1/bets", tags=["bets"])


class BetStatusRequest(BaseModel):
    status: Literal["ACCEPTED", "REJECTED"]


class BetVerifyRequest(BaseModel):
    approved: bool = True


async def _find_bet(session: AsyncSession, betId: int, user_id: int) -> Bet:
    bet = await session.scalar(select(Bet).join(Todo, Todo.id == Bet.todo_id).where(Bet.id == betId, Todo.user_id == user_id))
    if bet is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 내기입니다."})
    return bet


@router.patch("/{betId}/status")
async def update_bet_status(
    betId: int,
    payload: BetStatusRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    bet = await _find_bet(session, betId, user_id)
    bet.status = payload.status
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)


@router.post("/{betId}/proof")
async def upload_bet_proof(
    betId: int,
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    bet = await _find_bet(session, betId, user_id)
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        image = form.get("image")
        if not isinstance(image, UploadFile):
            raise HTTPException(status_code=400, detail={"message": "이미지 파일이 필요합니다."})
        bet.proof_image_url = await save_upload(image, "bet-proofs")
    else:
        raise HTTPException(status_code=400, detail={"message": "multipart/form-data로 이미지 파일을 첨부해야 합니다."})
    await session.commit()
    return {
        "success": True,
        "betId": betId,
        "proofImageUrl": bet.proof_image_url,
    }


@router.patch("/{betId}/verify")
async def verify_bet(
    betId: int,
    payload: BetVerifyRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    bet = await _find_bet(session, betId, user_id)
    bet.is_verified = payload.approved
    if payload.approved:
        bet.status = "VERIFIED"
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)
