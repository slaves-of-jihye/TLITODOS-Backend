from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import Bet, Todo, bet_to_response
from app.shared.uploads import save_upload


async def find_bet(session: AsyncSession, bet_id: int, user_id: int) -> Bet:
    bet = await session.scalar(select(Bet).join(Todo, Todo.id == Bet.todo_id).where(Bet.id == bet_id, Todo.user_id == user_id))
    if bet is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 내기입니다."})
    return bet


async def update_bet_status(session: AsyncSession, bet_id: int, payload, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id)
    bet.status = payload.status
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)


async def upload_bet_proof(session: AsyncSession, bet_id: int, form, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id)
    image = form.get("image")
    if not isinstance(image, UploadFile):
        raise HTTPException(status_code=400, detail={"message": "이미지 파일이 필요합니다."})
    bet.proof_image_url = await save_upload(image, "bet-proofs")
    await session.commit()
    return {"success": True, "betId": bet_id, "proofImageUrl": bet.proof_image_url}


async def verify_bet(session: AsyncSession, bet_id: int, payload, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id)
    bet.is_verified = payload.approved
    if payload.approved:
        bet.status = "VERIFIED"
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)
